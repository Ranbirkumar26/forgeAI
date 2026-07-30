from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forgeai.db.session import Base


def uuid_str() -> str:
    return str(uuid4())


class TaskRun(Base):
    __tablename__ = "task_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    task: Mapped[str] = mapped_column(Text)
    repo_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    model_profile: Mapped[str] = mapped_column(String(80), default="balanced")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    events: Mapped[list["RunEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="RunEvent.sequence"
    )
    steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["ApprovalRequest"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    verified_patches: Mapped[list["VerifiedPatch"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    llm_calls: Mapped[list["LLMCall"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class RunEvent(Base):
    __tablename__ = "run_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(ForeignKey("task_runs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, index=True)
    level: Mapped[str] = mapped_column(String(20), default="info")
    agent: Mapped[str | None] = mapped_column(String(80), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), default="log")
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run: Mapped[TaskRun] = relationship(back_populates="events")


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(ForeignKey("task_runs.id"), index=True)
    agent: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="completed")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    token_input: Mapped[int] = mapped_column(Integer, default=0)
    token_output: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    run: Mapped[TaskRun] = relationship(back_populates="steps")


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(ForeignKey("task_runs.id"), index=True)
    agent: Mapped[str] = mapped_column(String(80))
    tool_name: Mapped[str] = mapped_column(String(120))
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="planned")
    requires_approval: Mapped[bool] = mapped_column(default=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(ForeignKey("task_runs.id"), index=True)
    tool_call_id: Mapped[str | None] = mapped_column(ForeignKey("tool_calls.id"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    prompt: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(40), default="medium")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    run: Mapped[TaskRun] = relationship(back_populates="approvals")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(ForeignKey("task_runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run: Mapped[TaskRun] = relationship(back_populates="artifacts")


class VerifiedPatch(Base):
    __tablename__ = "verified_patches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(ForeignKey("task_runs.id"), index=True)
    base_sha: Mapped[str | None] = mapped_column(String(80), nullable=True)
    diff: Mapped[str] = mapped_column(Text)
    files_changed: Mapped[list] = mapped_column(JSON, default=list)
    lines_added: Mapped[int] = mapped_column(Integer, default=0)
    lines_removed: Mapped[int] = mapped_column(Integer, default=0)
    applies_cleanly: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    apply_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    checks: Mapped[list] = mapped_column(JSON, default=list)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    context_files_read: Mapped[list] = mapped_column(JSON, default=list)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    sandbox_image: Mapped[str] = mapped_column(String(160), default="local-verifier")
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run: Mapped[TaskRun] = relationship(back_populates="verified_patches")


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(ForeignKey("task_runs.id"), index=True)
    step_id: Mapped[str | None] = mapped_column(ForeignKey("agent_steps.id"), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, index=True)
    model: Mapped[str] = mapped_column(String(120))
    messages_hash: Mapped[str] = mapped_column(String(80), index=True)
    messages: Mapped[dict] = mapped_column(JSON, default=dict)
    response: Mapped[dict] = mapped_column(JSON, default=dict)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run: Mapped[TaskRun] = relationship(back_populates="llm_calls")


class RepoChunk(Base):
    __tablename__ = "repo_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    repo_path: Mapped[str] = mapped_column(Text, index=True)
    file_path: Mapped[str] = mapped_column(Text, index=True)
    language: Mapped[str] = mapped_column(String(40), default="text")
    symbol_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(60), default="file")
    start_line: Mapped[int] = mapped_column(Integer, default=1)
    end_line: Mapped[int] = mapped_column(Integer, default=1)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    docstring: Mapped[str | None] = mapped_column(Text, nullable=True)
    imports: Mapped[list] = mapped_column(JSON, default=list)
    content: Mapped[str] = mapped_column(Text)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    embedding_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MemoryRecord(Base):
    __tablename__ = "memory_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    scope: Mapped[str] = mapped_column(String(80), default="project")
    key: Mapped[str] = mapped_column(String(160), index=True)
    value: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source_run_id: Mapped[str | None] = mapped_column(ForeignKey("task_runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VisionFinding(Base):
    __tablename__ = "vision_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(ForeignKey("task_runs.id"), index=True)
    severity: Mapped[str] = mapped_column(String(40), default="info")
    finding_type: Mapped[str] = mapped_column(String(80), default="layout")
    message: Mapped[str] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
