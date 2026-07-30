"""current schema

Revision ID: 20260731_0001
Revises:
Create Date: 2026-07-31 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("repo_path", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("model_profile", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_task_runs_status", "task_runs", ["status"])

    op.create_table(
        "run_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("task_runs.id")),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("agent", sa.String(length=80), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])
    op.create_index("ix_run_events_sequence", "run_events", ["sequence"])

    op.create_table(
        "agent_steps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("task_runs.id")),
        sa.Column("agent", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("token_input", sa.Integer(), nullable=False),
        sa.Column("token_output", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"])

    op.create_table(
        "tool_calls",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("task_runs.id")),
        sa.Column("agent", sa.String(length=80), nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("command", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tool_calls_run_id", "tool_calls", ["run_id"])

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("task_runs.id")),
        sa.Column("tool_call_id", sa.String(length=36), sa.ForeignKey("tool_calls.id")),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.String(length=120), nullable=True),
    )
    op.create_index("ix_approval_requests_run_id", "approval_requests", ["run_id"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("task_runs.id")),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_artifacts_run_id", "artifacts", ["run_id"])

    op.create_table(
        "verified_patches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("task_runs.id")),
        sa.Column("base_sha", sa.String(length=80), nullable=True),
        sa.Column("diff", sa.Text(), nullable=False),
        sa.Column("files_changed", sa.JSON(), nullable=False),
        sa.Column("lines_added", sa.Integer(), nullable=False),
        sa.Column("lines_removed", sa.Integer(), nullable=False),
        sa.Column("applies_cleanly", sa.Boolean(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("apply_output", sa.Text(), nullable=True),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("context_files_read", sa.JSON(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("sandbox_image", sa.String(length=160), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_verified_patches_run_id", "verified_patches", ["run_id"])

    op.create_table(
        "llm_calls",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("task_runs.id")),
        sa.Column("step_id", sa.String(length=36), sa.ForeignKey("agent_steps.id")),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("messages_hash", sa.String(length=80), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_llm_calls_run_id", "llm_calls", ["run_id"])
    op.create_index("ix_llm_calls_sequence", "llm_calls", ["sequence"])
    op.create_index("ix_llm_calls_messages_hash", "llm_calls", ["messages_hash"])

    op.create_table(
        "repo_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("repo_path", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=40), nullable=False),
        sa.Column("symbol_path", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("docstring", sa.Text(), nullable=True),
        sa.Column("imports", sa.JSON(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("embedding_ref", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_repo_chunks_repo_path", "repo_chunks", ["repo_path"])
    op.create_index("ix_repo_chunks_file_path", "repo_chunks", ["file_path"])

    op.create_table(
        "memory_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scope", sa.String(length=80), nullable=False),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_run_id", sa.String(length=36), sa.ForeignKey("task_runs.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_memory_records_key", "memory_records", ["key"])

    op.create_table(
        "vision_findings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("task_runs.id")),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("finding_type", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("image_path", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_vision_findings_run_id", "vision_findings", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_vision_findings_run_id", table_name="vision_findings")
    op.drop_table("vision_findings")
    op.drop_index("ix_memory_records_key", table_name="memory_records")
    op.drop_table("memory_records")
    op.drop_index("ix_repo_chunks_file_path", table_name="repo_chunks")
    op.drop_index("ix_repo_chunks_repo_path", table_name="repo_chunks")
    op.drop_table("repo_chunks")
    op.drop_index("ix_llm_calls_messages_hash", table_name="llm_calls")
    op.drop_index("ix_llm_calls_sequence", table_name="llm_calls")
    op.drop_index("ix_llm_calls_run_id", table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_index("ix_verified_patches_run_id", table_name="verified_patches")
    op.drop_table("verified_patches")
    op.drop_index("ix_artifacts_run_id", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_approval_requests_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_run_id", table_name="approval_requests")
    op.drop_table("approval_requests")
    op.drop_index("ix_tool_calls_run_id", table_name="tool_calls")
    op.drop_table("tool_calls")
    op.drop_index("ix_agent_steps_run_id", table_name="agent_steps")
    op.drop_table("agent_steps")
    op.drop_index("ix_run_events_sequence", table_name="run_events")
    op.drop_index("ix_run_events_run_id", table_name="run_events")
    op.drop_table("run_events")
    op.drop_index("ix_task_runs_status", table_name="task_runs")
    op.drop_table("task_runs")
