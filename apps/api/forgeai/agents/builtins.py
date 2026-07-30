from pathlib import Path
from typing import Any

from sqlalchemy import select

from forgeai.core.config import get_settings
from forgeai.db.session import SessionLocal
from forgeai.db.tables import ApprovalRequest, ToolCall, VerifiedPatch
from forgeai.plugins import ForgePlugin, registry
from forgeai.services.events import (
    add_artifact,
    create_approval,
    create_tool_call,
    emit_event,
    record_step,
    set_run_status,
    write_artifact_file,
)
from forgeai.services.indexer import search_repository_context
from forgeai.services.memory import remember_run_summary
from forgeai.services.patches import (
    apply_verified_patch,
    build_readme_note_patch,
    create_verified_patch,
)
from forgeai.services.replay import record_llm_call
from forgeai.services.security import ApprovalPolicy, detect_suspicious_content


def planner_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    plan = [
        "Locate relevant repository context with keyword, symbol, and vector retrieval.",
        "Prepare one minimal VerifiedPatch with clean-apply evidence.",
        "Pause before mutation until approval resolves.",
        "Review provenance, risks, and documentation after apply.",
    ]
    settings = get_settings()
    with SessionLocal() as db:
        emit_event(
            db,
            run_id,
            "Planner produced a four-stage verified patch workflow.",
            agent="planner",
            event_type="agent_step",
            payload={"plan": plan, "model": settings.default_reasoning_model},
        )
        record_llm_call(
            db,
            run_id=run_id,
            model=settings.default_reasoning_model,
            messages={"task": state["task"], "role": "planner"},
            response={"plan": plan},
            tokens_in=420,
            tokens_out=180,
        )
        add_artifact(
            db,
            run_id,
            kind="plan",
            title="Verified Patch Plan",
            content="\n".join(f"{index + 1}. {item}" for index, item in enumerate(plan)),
        )
        record_step(db, run_id, "planner", "Produced verified patch work order.", token_input=420)
    return {**state, "plan": plan}


def engineer_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    repo_root = _repo_root(state)
    task = state["task"]
    settings = get_settings()
    with SessionLocal() as db:
        retrieved = search_repository_context(db, str(repo_root), task, limit=6)
        emit_event(
            db,
            run_id,
            f"Engineer retrieved {len(retrieved)} repository context chunks.",
            agent="engineer",
            event_type="retrieval",
            payload={"hits": _context_preview(retrieved)},
        )

        pending = _pending_patch_approval(db, run_id)
        if pending:
            emit_event(
                db,
                run_id,
                "Engineer paused at existing patch approval.",
                agent="engineer",
                event_type="agent_paused",
                payload={"approval_id": pending.id},
            )
            return {**state, "retrieved_chunks": retrieved, "halted": True}

        approved = _approved_patch_approval(db, run_id)
        if approved:
            patch = _latest_patch(db, run_id)
            if patch is None:
                raise RuntimeError("Approved run has no verified patch")
            applied = apply_verified_patch(db, patch, repo_root)
            create_tool_call(
                db,
                run_id,
                agent="engineer",
                tool_name="apply_patch",
                status="completed",
                requires_approval=True,
                payload={
                    "verified_patch_id": applied.id,
                    "applied_at": applied.applied_at.isoformat(),
                },
            )
            emit_event(
                db,
                run_id,
                "Approved VerifiedPatch applied to repository.",
                agent="engineer",
                event_type="patch_applied",
                payload={"verified_patch_id": applied.id, "files_changed": applied.files_changed},
            )
            record_step(
                db,
                run_id,
                "engineer",
                "Applied approved VerifiedPatch.",
                payload={"verified_patch_id": applied.id},
            )
            return {**state, "retrieved_chunks": retrieved, "verified_patch_id": applied.id}

        diff = build_readme_note_patch(repo_root, task)
        patch = create_verified_patch(
            db,
            run_id=run_id,
            repo_root=repo_root,
            diff=diff,
            context_files_read=_context_preview(retrieved),
            tokens_in=900,
            tokens_out=360,
        )
        record_llm_call(
            db,
            run_id=run_id,
            model=settings.default_reasoning_model,
            messages={"task": task, "context": _context_preview(retrieved), "role": "engineer"},
            response={"verified_patch_id": patch.id, "files_changed": patch.files_changed},
            tokens_in=900,
            tokens_out=360,
        )
        patch_path = write_artifact_file(run_id, "verified.patch", diff)
        add_artifact(
            db,
            run_id,
            kind="patch",
            title="VerifiedPatch Diff",
            path=str(patch_path),
            content=diff,
            payload={"verified_patch_id": patch.id, "applies_cleanly": patch.applies_cleanly},
        )
        if not patch.applies_cleanly:
            record_step(
                db,
                run_id,
                "engineer",
                "Prepared patch failed clean-apply verification.",
                status="failed",
                payload={"verified_patch_id": patch.id, "checks": patch.checks},
            )
            raise RuntimeError("Prepared patch failed clean-apply verification")

        policy = ApprovalPolicy(settings.approval_mode)
        tool_call = create_tool_call(
            db,
            run_id,
            agent="engineer",
            tool_name="apply_patch",
            requires_approval=policy.requires_approval("apply_patch"),
            payload={"verified_patch_id": patch.id, "artifact_path": str(patch_path)},
        )
        create_approval(
            db,
            run_id,
            action_type="apply_patch",
            tool_call_id=tool_call.id,
            prompt="Approve and apply verified patch after reviewing diff, checks, and provenance.",
            payload={
                "verified_patch_id": patch.id,
                "artifact_path": str(patch_path),
                "base_sha": patch.base_sha,
                "files_changed": patch.files_changed,
                "lines_added": patch.lines_added,
                "lines_removed": patch.lines_removed,
                "checks": patch.checks,
                "provenance": patch.provenance,
            },
        )
        set_run_status(db, run_id, "awaiting_approval")
        record_step(
            db,
            run_id,
            "engineer",
            "Prepared VerifiedPatch and requested approval.",
            status="paused",
            payload={"verified_patch_id": patch.id},
        )
    return {**state, "retrieved_chunks": retrieved, "verified_patch_id": patch.id, "halted": True}


def approval_gate_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    with SessionLocal() as db:
        pending = db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.run_id == run_id,
                ApprovalRequest.status == "pending",
            )
        ).scalar_one_or_none()
        if pending:
            emit_event(
                db,
                run_id,
                "Run paused at approval gate.",
                agent="approval-gate",
                level="warning",
                event_type="approval_waiting",
                payload={"approval_id": pending.id},
            )
            return {**state, "halted": True}
        emit_event(
            db,
            run_id,
            "Approval gate clear.",
            agent="approval-gate",
            event_type="approval_clear",
        )
    return {**state, "halted": False}


def reviewer_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    with SessionLocal() as db:
        patch = _latest_patch(db, run_id)
        tool_calls = db.execute(select(ToolCall).where(ToolCall.run_id == run_id)).scalars().all()
        suspicious = _suspicious_context(state.get("retrieved_chunks", []))
        if suspicious:
            emit_event(
                db,
                run_id,
                f"Reviewer found {len(suspicious)} suspicious context lines.",
                agent="reviewer",
                level="warning",
                event_type="prompt_injection_signal",
                payload={"findings": suspicious},
            )
        checks = patch.checks if patch else []
        content = (
            "Review summary:\n"
            f"- Files changed: {', '.join(patch.files_changed) if patch else 'none'}\n"
            f"- Checks passed: {_passed_checks(checks)} of {len(checks)}\n"
            f"- Mutating tool calls: {sum(1 for call in tool_calls if call.requires_approval)}\n"
            f"- Suspicious retrieved lines: {len(suspicious)}\n"
        )
        add_artifact(db, run_id, kind="review", title="VerifiedPatch Review", content=content)
        record_step(
            db,
            run_id,
            "reviewer",
            "Reviewed checks, approvals, and retrieved context risks.",
            payload={"suspicious_findings": suspicious, "tool_calls": len(tool_calls)},
        )
    return state


def documenter_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    task = state["task"]
    with SessionLocal() as db:
        patch = _latest_patch(db, run_id)
        changed = ", ".join(patch.files_changed) if patch else "none"
        changelog = (
            "## Unreleased\n\n"
            f"- Applied approved ForgeAI VerifiedPatch for: {task}\n"
            f"- Changed files: {changed}\n"
        )
        add_artifact(
            db,
            run_id,
            kind="changelog",
            title="Changelog Entry",
            content=changelog,
            payload={"verified_patch_id": patch.id if patch else None},
        )
        remember_run_summary(
            db,
            run_id,
            task,
            f"VerifiedPatch workflow completed. Changed files: {changed}.",
        )
        emit_event(
            db,
            run_id,
            "Documenter generated changelog and stored project memory.",
            agent="documenter",
            event_type="docs_generated",
        )
        record_step(db, run_id, "documenter", "Generated changelog and memory summary.")
    return {**state, "summary": "VerifiedPatch workflow completed."}


def register_builtin_plugins() -> None:
    plugins = [
        ForgePlugin(
            "planner",
            ("task_decomposition", "verified_patch_work_order"),
            node_builder=lambda: planner_node,
        ),
        ForgePlugin(
            "engineer",
            ("repo_context", "patch_generation", "clean_apply_verification"),
            node_builder=lambda: engineer_node,
        ),
        ForgePlugin(
            "reviewer",
            ("approval_audit", "prompt_injection_scan", "risk_review"),
            node_builder=lambda: reviewer_node,
        ),
        ForgePlugin(
            "documenter",
            ("changelog", "memory_summary"),
            node_builder=lambda: documenter_node,
        ),
    ]
    for plugin in plugins:
        registry.register(plugin)


def _repo_root(state: dict[str, Any]) -> Path:
    root = Path(state.get("repo_path") or get_settings().workspace_root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {root}")
    return root


def _pending_patch_approval(db, run_id: str) -> ApprovalRequest | None:
    return db.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.run_id == run_id,
            ApprovalRequest.action_type == "apply_patch",
            ApprovalRequest.status == "pending",
        )
    ).scalar_one_or_none()


def _approved_patch_approval(db, run_id: str) -> ApprovalRequest | None:
    return db.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.run_id == run_id,
            ApprovalRequest.action_type == "apply_patch",
            ApprovalRequest.status == "approved",
        )
    ).scalar_one_or_none()


def _latest_patch(db, run_id: str) -> VerifiedPatch | None:
    return (
        db.execute(
            select(VerifiedPatch)
            .where(VerifiedPatch.run_id == run_id)
            .order_by(VerifiedPatch.created_at.desc())
        )
        .scalars()
        .first()
    )


def _context_preview(chunks: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "file_path": chunk.get("file_path"),
            "score": chunk.get("score"),
            "language": chunk.get("language"),
            "symbol_path": chunk.get("symbol_path"),
            "start_line": chunk.get("start_line"),
            "end_line": chunk.get("end_line"),
            "preview": str(chunk.get("preview") or chunk.get("content") or "")[:260],
            "retrieval_mode": chunk.get("retrieval_mode"),
        }
        for chunk in chunks
    ]


def _suspicious_context(chunks: list[dict[str, object]]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for chunk in chunks:
        file_path = str(chunk.get("file_path") or "unknown")
        content = str(chunk.get("content") or chunk.get("preview") or "")
        findings.extend(detect_suspicious_content(file_path, content))
    return findings[:20]


def _passed_checks(checks: list[dict[str, object]]) -> int:
    return sum(1 for check in checks if int(check.get("exit_code", 1)) == 0)
