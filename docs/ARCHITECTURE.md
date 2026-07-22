# ForgeAI Architecture

ForgeAI is built around a small control plane and plugin-driven agent graph.

## Runtime

- FastAPI exposes task, approval, repository indexing, search, health, and metrics APIs.
- LangGraph coordinates deterministic agent nodes for the local MVP.
- Celery and Redis run the graph asynchronously in Docker; inline mode keeps local development simple.
- SQLAlchemy persists runs, events, steps, approvals, artifacts, chunks, memories, tool calls, and vision findings.
- Qdrant stores repository embeddings when available; a deterministic in-memory vector store keeps tests and offline demos working.
- OpenTelemetry instrumentation and Prometheus metrics are enabled from the first version.

## Agents

- Planner decomposes work.
- Repo RAG retrieves indexed code context.
- Coder prepares patches and stops at approval.
- Testing records safe checks.
- Vision creates before/after OpenCV diff artifacts.
- Security audits tool calls and approvals.
- Review produces risk-focused notes.
- Docs creates changelog and social artifacts.
- Deployment is present but disabled by default.
- Memory stores run summaries for future personalization.

## Plugin Contract

Each plugin declares:

- `name`
- `capabilities`
- `required_env`
- `approval_policy`
- `enabled_by_default`
- optional LangGraph node builder

This keeps future MCP, GitHub, Railway, Vercel, Supabase, Browser Use, and model-provider tools addable without rewriting the orchestrator.

## Security-Critical Design Choices

- Mutating tool actions are modeled as `ToolCall` plus `ApprovalRequest`.
- The graph halts at `approval-gate` when approvals are pending.
- Cloud deployment is represented by a disabled-by-default plugin path.
- Repository indexing has deterministic local fallback behavior for tests.
- The current MVP is not an execution sandbox; see `docs/SECURITY_AND_VULNERABILITIES.md` before adding real file writes, shell execution, browser automation, git push, or deployment.
