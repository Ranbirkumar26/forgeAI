# ForgeAI Architecture

ForgeAI is built around a small control plane, durable run records, and an approval-gated patch workflow.

## Runtime

- FastAPI exposes task, approval, repository indexing, search, health, and metrics APIs.
- LangGraph coordinates deterministic agent nodes for the local MVP.
- Inline background tasks are the default local runner.
- Celery and Redis remain available for Docker mode.
- SQLAlchemy persists runs, events, steps, tool calls, approvals, artifacts, verified patches, replay calls, repository chunks, and memory.
- SQLite is the default database.
- Postgres is optional in Docker.
- Qdrant stores repository embeddings when available.
- In-memory vector fallback keeps tests and offline demos deterministic.
- OpenTelemetry instrumentation and Prometheus metrics are enabled.

## Graph

```text
planner -> engineer -> approval-gate
  -> reviewer -> documenter
```

## Agents

- Planner creates a verified patch work order and replay record.
- Engineer retrieves repository context, builds a minimal patch, verifies clean apply, requests approval, and applies approved patches.
- Approval Gate halts when any approval is pending.
- Reviewer audits checks, approvals, tool calls, and suspicious retrieved content.
- Documenter creates changelog artifact and stores memory summary.

## VerifiedPatch

`VerifiedPatch` is the central artifact.

Fields include:

- `base_sha`
- `diff`
- `files_changed`
- `lines_added`
- `lines_removed`
- `applies_cleanly`
- `checks`
- `context_files_read`
- `tokens_in`
- `tokens_out`
- `cost_usd`
- `sandbox_image`
- `provenance`
- `applied_at`
- `apply_output`

Current verification runs locally:

- `git apply --check --whitespace=nowarn -`
- internal diff secret scan

The `sandbox_image` value is currently `local-verifier:no-container` to make the sandbox gap explicit.

## Repository Intelligence

Indexer behavior:

- skips dependency, cache, build, test-output, and runtime-artifact folders
- respects `.forgeignore`
- skips sensitive file names
- caps indexed file size
- skips files containing likely secrets
- extracts lightweight symbols from Python, TypeScript, and JavaScript
- records line ranges, imports, signatures, and docstrings
- stores chunks in SQL
- writes vectors to Qdrant when available
- falls back to in-memory vectors

Retrieval order:

1. keyword and symbol match from SQL chunks
2. vector fallback

## Plugin Contract

Each plugin declares:

- `name`
- `capabilities`
- `required_env`
- `approval_policy`
- `enabled_by_default`
- optional LangGraph node builder

This keeps MCP, GitHub, Railway, Vercel, Supabase, Browser Use, Playwright, and model-provider tools addable without rewriting API routes.

## Security-Critical Design Choices

- Mutating actions are represented as `ToolCall` plus `ApprovalRequest`.
- Patch application uses approval status before `git apply`.
- Rejection requires reason.
- Retrieved content is treated as untrusted and scanned for prompt-injection signals.
- Cloud and browser plugins are not enabled by default.
- The current MVP is not a container sandbox. See `docs/SECURITY_AND_VULNERABILITIES.md` before adding real shell, browser, git push, deploy, or cloud-provider behavior.
