from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from forgeai.core.config import get_settings
from forgeai.db.tables import AgentStep, ApprovalRequest, Artifact, RunEvent, TaskRun, ToolCall
from forgeai.services.security import redact_secrets, summarize_risk


def next_sequence(db: Session, run_id: str) -> int:
    value = db.execute(
        select(func.max(RunEvent.sequence)).where(RunEvent.run_id == run_id)
    ).scalar()
    return int(value or 0) + 1


def emit_event(
    db: Session,
    run_id: str,
    message: str,
    *,
    agent: str | None = None,
    level: str = "info",
    event_type: str = "log",
    payload: dict[str, Any] | None = None,
) -> RunEvent:
    event = RunEvent(
        run_id=run_id,
        sequence=next_sequence(db, run_id),
        level=level,
        agent=agent,
        event_type=event_type,
        message=redact_secrets(message),
        payload=payload or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def record_step(
    db: Session,
    run_id: str,
    agent: str,
    summary: str,
    *,
    status: str = "completed",
    token_input: int = 0,
    token_output: int = 0,
    payload: dict[str, Any] | None = None,
) -> AgentStep:
    step = AgentStep(
        run_id=run_id,
        agent=agent,
        status=status,
        summary=redact_secrets(summary),
        completed_at=datetime.utcnow(),
        token_input=token_input,
        token_output=token_output,
        payload=payload or {},
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def add_artifact(
    db: Session,
    run_id: str,
    *,
    kind: str,
    title: str,
    content: str | None = None,
    path: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Artifact:
    artifact = Artifact(
        run_id=run_id,
        kind=kind,
        title=title,
        content=redact_secrets(content) if content else None,
        path=path,
        payload=payload or {},
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    emit_event(
        db,
        run_id,
        f"Created artifact: {title}",
        agent="artifact-store",
        event_type="artifact",
        payload={"artifact_id": artifact.id, "kind": kind},
    )
    return artifact


def write_artifact_file(run_id: str, filename: str, content: str | bytes) -> Path:
    settings = get_settings()
    run_dir = settings.artifact_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / filename
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def create_tool_call(
    db: Session,
    run_id: str,
    *,
    agent: str,
    tool_name: str,
    command: str | None = None,
    status: str = "planned",
    requires_approval: bool = False,
    payload: dict[str, Any] | None = None,
) -> ToolCall:
    tool_call = ToolCall(
        run_id=run_id,
        agent=agent,
        tool_name=tool_name,
        command=redact_secrets(command) if command else None,
        status=status,
        requires_approval=requires_approval,
        payload=payload or {},
    )
    db.add(tool_call)
    db.commit()
    db.refresh(tool_call)
    emit_event(
        db,
        run_id,
        f"Planned tool call: {tool_name}",
        agent=agent,
        event_type="tool_call",
        payload={"tool_call_id": tool_call.id, "requires_approval": requires_approval},
    )
    return tool_call


def create_approval(
    db: Session,
    run_id: str,
    *,
    action_type: str,
    prompt: str,
    tool_call_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> ApprovalRequest:
    existing = db.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.run_id == run_id,
            ApprovalRequest.action_type == action_type,
            ApprovalRequest.status == "pending",
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    approval = ApprovalRequest(
        run_id=run_id,
        tool_call_id=tool_call_id,
        action_type=action_type,
        prompt=prompt,
        risk_level=summarize_risk(action_type),
        payload=payload or {},
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    emit_event(
        db,
        run_id,
        prompt,
        agent="approval-gate",
        level="warning",
        event_type="approval_requested",
        payload={"approval_id": approval.id, "action_type": action_type},
    )
    return approval


def set_run_status(db: Session, run_id: str, status: str) -> None:
    run = db.get(TaskRun, run_id)
    if run:
        run.status = status
        if status in {"completed", "failed", "rejected"}:
            run.completed_at = datetime.utcnow()
        db.add(run)
        db.commit()
