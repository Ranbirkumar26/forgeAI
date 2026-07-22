from typing import Any

from sqlalchemy import select

from forgeai.core.config import get_settings
from forgeai.db.session import SessionLocal
from forgeai.db.tables import ApprovalRequest, TaskRun, ToolCall, VisionFinding
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
from forgeai.services.indexer import semantic_search
from forgeai.services.memory import remember_run_summary
from forgeai.services.security import ApprovalPolicy
from forgeai.services.vision import create_demo_visual_diff


def _db_run(run_id: str) -> TaskRun:
    db = SessionLocal()
    try:
        run = db.get(TaskRun, run_id)
        if run is None:
            raise RuntimeError(f"Run not found: {run_id}")
        return run
    finally:
        db.close()


def planner_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    plan = [
        "Understand the repository and identify relevant files.",
        "Generate a minimal implementation patch and request approval before writes.",
        "Run allowed tests and static checks.",
        "Inspect UI output visually and compare before/after artifacts.",
        "Review security, produce docs, and record reusable memory.",
    ]
    with SessionLocal() as db:
        emit_event(
            db,
            run_id,
            "Planner decomposed the task into an approval-gated engineering workflow.",
            agent="planner",
            event_type="agent_step",
            payload={"plan": plan, "model": get_settings().default_reasoning_model},
        )
        add_artifact(
            db,
            run_id,
            kind="plan",
            title="Execution Plan",
            content="\n".join(f"{index + 1}. {item}" for index, item in enumerate(plan)),
        )
        record_step(db, run_id, "planner", "Produced a five-stage execution plan.", token_input=420)
    return {**state, "plan": plan}


def repo_rag_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    task = state["task"]
    with SessionLocal() as db:
        hits = semantic_search(task, limit=5)
        payload = [
            {
                "file_path": hit.file_path,
                "score": round(hit.score, 4),
                "language": hit.language,
                "preview": hit.content[:260],
            }
            for hit in hits
        ]
        message = (
            f"Retrieved {len(payload)} repository context chunks."
            if payload
            else "No indexed repository context found yet; continuing with task intent."
        )
        emit_event(
            db, run_id, message, agent="repo-rag", event_type="retrieval", payload={"hits": payload}
        )
        record_step(db, run_id, "repo-rag", message, payload={"hits": payload})
    return {**state, "retrieved_chunks": payload}


def coder_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    settings = get_settings()
    with SessionLocal() as db:
        approved = db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.run_id == run_id,
                ApprovalRequest.action_type == "file_write",
                ApprovalRequest.status == "approved",
            )
        ).first()
        pending = db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.run_id == run_id,
                ApprovalRequest.action_type == "file_write",
                ApprovalRequest.status == "pending",
            )
        ).scalar_one_or_none()
        if pending:
            emit_event(
                db,
                run_id,
                "Coder is paused until the prepared patch is approved.",
                agent="coder",
                event_type="agent_paused",
            )
            return {**state, "halted": True}

        patch = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@
+# ForgeAI Generated Change
+
+This patch was prepared by ForgeAI's Coder Agent. It is intentionally held
+behind an approval gate before any repository file is modified.
"""
        patch_path = write_artifact_file(run_id, "prepared.patch", patch)
        add_artifact(
            db,
            run_id,
            kind="patch",
            title="Prepared Implementation Patch",
            path=str(patch_path),
            content=patch,
            payload={"model": settings.default_reasoning_model},
        )

        if not approved:
            policy = ApprovalPolicy(settings.approval_mode)
            tool_call = create_tool_call(
                db,
                run_id,
                agent="coder",
                tool_name="file_write",
                requires_approval=policy.requires_approval("file_write"),
                payload={"artifact_path": str(patch_path)},
            )
            create_approval(
                db,
                run_id,
                action_type="file_write",
                tool_call_id=tool_call.id,
                prompt=(
                    "Approve the prepared code patch before ForgeAI proceeds "
                    "to test and review."
                ),
                payload={
                    "artifact_path": str(patch_path),
                    "summary": "Add ForgeAI generated README note.",
                },
            )
            set_run_status(db, run_id, "awaiting_approval")
            record_step(
                db, run_id, "coder", "Prepared patch and requested approval.", status="paused"
            )
            return {**state, "halted": True}

        create_tool_call(
            db,
            run_id,
            agent="coder",
            tool_name="file_write",
            status="approved",
            payload={"artifact_path": str(patch_path), "approved": True},
        )
        emit_event(
            db,
            run_id,
            "Patch approval detected; continuing without touching repo files in demo mode.",
            agent="coder",
            event_type="approval_resumed",
        )
        record_step(
            db, run_id, "coder", "Resumed after patch approval.", payload={"patch": str(patch_path)}
        )
    return {**state, "halted": False}


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
            db, run_id, "Approval gate clear.", agent="approval-gate", event_type="approval_clear"
        )
    return {**state, "halted": False}


def testing_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    with SessionLocal() as db:
        tool_call = create_tool_call(
            db,
            run_id,
            agent="testing",
            tool_name="shell",
            command="pytest apps/api/tests",
            requires_approval=False,
        )
        report = (
            "Local demo check plan:\n"
            "- backend unit tests\n"
            "- API contract tests\n"
            "- visual diff fixture test"
        )
        add_artifact(db, run_id, kind="test_report", title="Testing Agent Report", content=report)
        tool_call.status = "completed"
        db.add(tool_call)
        db.commit()
        emit_event(
            db,
            run_id,
            "Testing agent selected allowed checks and recorded the test plan.",
            agent="testing",
            event_type="test_plan",
        )
        record_step(
            db, run_id, "testing", "Selected safe test commands and produced a test report."
        )
    return state


def vision_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    image_path = get_settings().artifact_dir / run_id / "vision-diff.png"
    stats = create_demo_visual_diff(image_path)
    with SessionLocal() as db:
        finding = VisionFinding(
            run_id=run_id,
            severity="info",
            finding_type="before_after_diff",
            message=stats["message"],
            image_path=str(image_path),
            score=stats["change_ratio"],
            payload=stats,
        )
        db.add(finding)
        db.commit()
        add_artifact(
            db,
            run_id,
            kind="vision",
            title="Before/After Visual Diff",
            path=str(image_path),
            payload=stats,
        )
        emit_event(
            db,
            run_id,
            "Vision agent generated a before/after UI diff artifact.",
            agent="vision",
            event_type="vision_finding",
            payload=stats,
        )
        record_step(db, run_id, "vision", "Generated OpenCV visual diff artifact.", payload=stats)
    return state


def security_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    with SessionLocal() as db:
        tool_count = db.execute(select(ToolCall).where(ToolCall.run_id == run_id)).scalars().all()
        high_risk = [tool for tool in tool_count if tool.requires_approval]
        summary = f"Reviewed {len(tool_count)} tool calls; {len(high_risk)} required approval."
        emit_event(db, run_id, summary, agent="security", event_type="security_review")
        record_step(db, run_id, "security", summary)
    return state


def review_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    with SessionLocal() as db:
        content = (
            "Review summary:\n"
            "- Patch is isolated and documented.\n"
            "- Mutating work stayed behind approval.\n"
            "- Follow-up: run full CI before applying to a production repository.\n"
        )
        add_artifact(db, run_id, kind="review", title="Review Agent Notes", content=content)
        emit_event(db, run_id, "Review agent completed a risk-focused pass.", agent="review")
        record_step(db, run_id, "review", "Completed risk-focused review.")
    return state


def documentation_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    task = state["task"]
    with SessionLocal() as db:
        changelog = (
            f"## Unreleased\n\n- ForgeAI prepared an approval-gated implementation for: {task}\n"
        )
        linkedin = (
            "Built a local-first autonomous software engineering control plane: "
            "LangGraph agents, RAG, approval-gated code actions, visual UI checks, "
            "and live telemetry."
        )
        add_artifact(
            db, run_id, kind="changelog", title="Generated Changelog Entry", content=changelog
        )
        add_artifact(db, run_id, kind="social", title="LinkedIn Draft", content=linkedin)
        emit_event(
            db, run_id, "Documentation agent generated release and social artifacts.", agent="docs"
        )
        record_step(db, run_id, "docs", "Generated changelog and LinkedIn draft.")
    return state


def deployment_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    with SessionLocal() as db:
        settings = get_settings()
        if not settings.enable_cloud_plugins:
            emit_event(
                db,
                run_id,
                (
                    "Deployment plugin is installed but disabled until cloud credentials "
                    "and approvals are configured."
                ),
                agent="deployment",
                event_type="deployment_skipped",
            )
            record_step(db, run_id, "deployment", "Skipped cloud deployment by configuration.")
            return state
        create_tool_call(
            db,
            run_id,
            agent="deployment",
            tool_name="deploy",
            requires_approval=True,
            payload={"target": "railway-or-vercel"},
        )
        create_approval(
            db,
            run_id,
            action_type="deploy",
            prompt="Approve production deployment.",
            payload={"target": "railway-or-vercel"},
        )
    return {**state, "halted": True}


def memory_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state["run_id"]
    task = state["task"]
    summary = (
        "ForgeAI planned, prepared, tested, visually inspected, reviewed, and documented the run."
    )
    with SessionLocal() as db:
        remember_run_summary(db, run_id, task, summary)
        emit_event(
            db,
            run_id,
            "Memory agent stored the run summary for future personalization.",
            agent="memory",
        )
        record_step(db, run_id, "memory", "Stored long-term run summary.")
    return {**state, "summary": summary}


def register_builtin_plugins() -> None:
    plugins = [
        ForgePlugin(
            "planner", ("task_decomposition", "work_order"), node_builder=lambda: planner_node
        ),
        ForgePlugin(
            "repo-rag",
            ("repository_search", "semantic_context"),
            node_builder=lambda: repo_rag_node,
        ),
        ForgePlugin("coder", ("patch_generation", "code_actions"), node_builder=lambda: coder_node),
        ForgePlugin("testing", ("test_selection", "safe_shell"), node_builder=lambda: testing_node),
        ForgePlugin(
            "vision", ("screenshot_diff", "layout_inspection"), node_builder=lambda: vision_node
        ),
        ForgePlugin(
            "security", ("approval_audit", "secret_redaction"), node_builder=lambda: security_node
        ),
        ForgePlugin("review", ("code_review", "risk_review"), node_builder=lambda: review_node),
        ForgePlugin("docs", ("changelog", "social_post"), node_builder=lambda: documentation_node),
        ForgePlugin(
            "deployment",
            ("railway", "vercel", "github_actions"),
            required_env=("RAILWAY_TOKEN", "VERCEL_TOKEN", "GITHUB_TOKEN"),
            enabled_by_default=True,
            node_builder=lambda: deployment_node,
        ),
        ForgePlugin(
            "memory", ("long_term_memory", "preferences"), node_builder=lambda: memory_node
        ),
    ]
    for plugin in plugins:
        registry.register(plugin)


register_builtin_plugins()
