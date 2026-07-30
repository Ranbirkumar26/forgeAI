from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class RunCreate(BaseModel):
    task: str = Field(min_length=3)
    repo_path: str | None = None
    model_profile: Literal["reasoning", "balanced", "economy"] = "balanced"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepoIndexRequest(BaseModel):
    path: str
    include_globs: list[str] = Field(default_factory=list)
    exclude_globs: list[str] = Field(default_factory=list)


class SearchResponseItem(BaseModel):
    file_path: str
    content: str
    score: float
    language: str = "text"


class ApprovalDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    actor: str = "local-user"
    reason: str | None = None

    @model_validator(mode="after")
    def require_rejection_reason(self) -> "ApprovalDecision":
        if self.decision == "rejected" and not self.reason:
            raise ValueError("Rejection reason is required")
        return self


class RunEventRead(BaseModel):
    id: str
    run_id: str
    sequence: int
    level: str
    agent: str | None
    event_type: str
    message: str
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentStepRead(BaseModel):
    id: str
    run_id: str
    agent: str
    status: str
    summary: str
    token_input: int
    token_output: int
    payload: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ApprovalRequestRead(BaseModel):
    id: str
    run_id: str
    action_type: str
    status: str
    prompt: str
    risk_level: str
    payload: dict[str, Any]
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class ArtifactRead(BaseModel):
    id: str
    run_id: str
    kind: str
    title: str
    path: str | None
    content: str | None
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class VerifiedPatchRead(BaseModel):
    id: str
    run_id: str
    base_sha: str | None
    diff: str
    files_changed: list[Any]
    lines_added: int
    lines_removed: int
    applies_cleanly: bool
    applied_at: datetime | None
    apply_output: str | None
    checks: list[Any]
    attempts: int
    context_files_read: list[Any]
    tokens_in: int
    tokens_out: int
    cost_usd: float
    sandbox_image: str
    provenance: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class LLMCallRead(BaseModel):
    id: str
    run_id: str
    step_id: str | None
    sequence: int
    model: str
    messages_hash: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_usd: float
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskRunRead(BaseModel):
    id: str
    task: str
    repo_path: str | None
    status: str
    model_profile: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    events: list[RunEventRead] = Field(default_factory=list)
    steps: list[AgentStepRead] = Field(default_factory=list)
    approvals: list[ApprovalRequestRead] = Field(default_factory=list)
    artifacts: list[ArtifactRead] = Field(default_factory=list)
    verified_patches: list[VerifiedPatchRead] = Field(default_factory=list)
    llm_calls: list[LLMCallRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}
