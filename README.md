# ForgeAI

ForgeAI is a local-first software engineering control plane for verified, approval-gated code changes. It is built as a production-style monorepo with a FastAPI and LangGraph backend, a Next.js dashboard, repository indexing, deterministic retrieval, durable run history, human approval gates, and first-class patch evidence.

The MVP is centered on one artifact: `VerifiedPatch`.

A run is not considered valuable because an agent wrote text. A run is valuable when it produces an evidence-backed patch that a human can inspect, approve, apply, reject, replay, and audit.

## Current Status

Implemented:

- FastAPI API with task runs, approvals, repository indexing, search, health, metrics, and SSE events.
- LangGraph orchestration with four built-in agents: Planner, Engineer, Reviewer, and Documenter.
- Approval gate that halts before mutating patch application.
- `VerifiedPatch` persistence with diff, base SHA, changed files, line counts, clean-apply result, checks, provenance, token metrics, and apply status.
- Local patch verifier using `git apply --check` and internal diff secret scanning.
- Approved patch application using `git apply`.
- Repository indexing with sensitive-path exclusion, file-size limits, `.forgeignore`, lightweight symbol-aware chunking, deterministic embeddings, Qdrant when available, and in-memory fallback.
- Prompt-injection signal detection for retrieved context.
- Replay scaffolding through `LLMCall` records without requiring live model calls.
- Next.js dashboard focused on run trace, approval evidence, unified diff, checks, artifacts, vector search, and token/tool usage.
- Docker Compose for local full stack.
- CI workflow for backend tests, frontend build, lint, and Docker smoke checks.
- Security and vulnerability documentation for future agents.

Not implemented yet:

- Locked-down container sandbox for file, shell, browser, git, and deploy actions.
- Tree-sitter indexer.
- ONNX or transformer embedding runtime.
- Real provider LLM calls.
- Playwright screenshot capture and computer-vision review as a default workflow.
- GitHub PR creation, git push, Railway deploy, Vercel deploy, Supabase cloud setup, and browser-form automation.
- API authentication, ownership, quotas, and production CORS controls.

Those items are deferred, not rejected. See `AGENTS.md` and `docs/SECURITY_AND_VULNERABILITIES.md`.

## Feature Tree

```text
ForgeAI
|
+-- Control Plane
|   |
|   +-- TaskRun lifecycle
|   |   +-- queued
|   |   +-- running
|   |   +-- awaiting_approval
|   |   +-- completed
|   |   +-- rejected
|   |   +-- failed
|   |
|   +-- RunEvent stream
|   |   +-- persisted sequence numbers
|   |   +-- Server-Sent Events endpoint
|   |   +-- dashboard polling fallback
|   |
|   +-- AgentStep history
|   |   +-- status
|   |   +-- summary
|   |   +-- token counts
|   |   +-- structured payload
|   |
|   +-- Artifact store
|       +-- plan
|       +-- patch
|       +-- review
|       +-- changelog
|
+-- Agent Graph
|   |
|   +-- Planner
|   |   +-- creates verified patch work order
|   |   +-- records replay metadata
|   |   +-- emits plan artifact
|   |
|   +-- Engineer
|   |   +-- retrieves repository context
|   |   +-- builds minimal patch
|   |   +-- verifies clean apply
|   |   +-- scans diff for likely secrets
|   |   +-- requests approval before apply
|   |   +-- applies approved patch
|   |
|   +-- Approval Gate
|   |   +-- halts on pending approval
|   |   +-- resumes after approval resolution
|   |
|   +-- Reviewer
|   |   +-- audits tool calls
|   |   +-- checks approval coverage
|   |   +-- reports suspicious retrieved content
|   |   +-- writes review artifact
|   |
|   +-- Documenter
|       +-- writes changelog artifact
|       +-- stores memory summary
|
+-- VerifiedPatch
|   |
|   +-- Patch identity
|   |   +-- id
|   |   +-- run_id
|   |   +-- base_sha
|   |
|   +-- Diff evidence
|   |   +-- unified diff
|   |   +-- files_changed
|   |   +-- lines_added
|   |   +-- lines_removed
|   |
|   +-- Verification evidence
|   |   +-- applies_cleanly
|   |   +-- git apply check
|   |   +-- diff secret scan
|   |   +-- attempts
|   |   +-- provenance
|   |
|   +-- Apply evidence
|   |   +-- applied_at
|   |   +-- apply_output
|   |
|   +-- Cost and replay
|       +-- tokens_in
|       +-- tokens_out
|       +-- cost_usd
|       +-- context_files_read
|
+-- Repository Intelligence
|   |
|   +-- Local indexing
|   |   +-- `.forgeignore`
|   |   +-- ignored dependency/build folders
|   |   +-- sensitive-path exclusion
|   |   +-- max file size cap
|   |   +-- secret-content skip
|   |
|   +-- Chunking
|   |   +-- markdown and config text chunks
|   |   +-- lightweight Python symbols
|   |   +-- lightweight TypeScript and JavaScript symbols
|   |   +-- import extraction
|   |   +-- line ranges
|   |
|   +-- Retrieval
|       +-- keyword and symbol search
|       +-- deterministic local embeddings
|       +-- Qdrant optional path
|       +-- in-memory vector fallback
|
+-- Safety
|   |
|   +-- ApprovalPolicy
|   |   +-- file writes
|   |   +-- patch application
|   |   +-- shell mutations
|   |   +-- git push
|   |   +-- GitHub PR
|   |   +-- deploy
|   |   +-- browser form action
|   |
|   +-- Redaction
|   |   +-- common API keys
|   |   +-- GitHub tokens
|   |   +-- OpenAI-style keys
|   |   +-- private key blocks
|   |
|   +-- Prompt-injection signals
|       +-- ignore previous instructions
|       +-- reveal system prompt
|       +-- print `.env`
|       +-- disable approval checks
|       +-- exfiltration language
|
+-- Dashboard
|   |
|   +-- Run composer
|   +-- Repository index action
|   +-- Approval screen
|   |   +-- diff stats
|   |   +-- checks
|   |   +-- equal-weight reject and approve controls
|   |   +-- required rejection reason
|   |
|   +-- Run trace
|   |   +-- status
|   |   +-- run id copy
|   |   +-- base SHA copy
|   |   +-- event stream
|   |
|   +-- VerifiedPatch view
|   |   +-- clean apply status
|   |   +-- applied status
|   |   +-- attempts
|   |   +-- cost
|   |   +-- unified diff
|   |
|   +-- Artifacts
|   +-- Vector search
|
+-- Observability
|   |
|   +-- Prometheus metrics
|   +-- OpenTelemetry FastAPI instrumentation
|   +-- structured events
|   +-- token and cost records
|
+-- Optional Infrastructure
    |
    +-- Docker Compose
    |   +-- API
    |   +-- web
    |   +-- worker
    |   +-- Postgres
    |   +-- Redis
    |   +-- Qdrant
    |
    +-- Disabled-by-default cloud plugins
        +-- GitHub
        +-- Railway
        +-- Vercel
        +-- Supabase
```

## Quick Start

From the repository root:

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -e "apps/api[dev]"
pnpm install
```

Run the backend:

```bash
source .venv/bin/activate
uvicorn forgeai.main:app --app-dir apps/api --reload
```

Run the dashboard in another terminal:

```bash
pnpm dev
```

Open:

- Dashboard: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/healthz`
- Prometheus metrics: `http://localhost:8000/metrics`

Alternate ports:

```bash
uvicorn forgeai.main:app --app-dir apps/api --host 127.0.0.1 --port 8002 --reload
NEXT_PUBLIC_API_URL=http://127.0.0.1:8002 pnpm --dir apps/web exec next dev --hostname 127.0.0.1 --port 3002
```

## Demo Script

Use the included sample repository or any small local git repository with a `README.md`.

Index the sample repo:

```bash
curl -X POST http://localhost:8000/api/repos/index \
  -H "Content-Type: application/json" \
  -d '{"path":"examples/sample-repo"}'
```

Create a run:

```bash
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{"task":"Prepare a safe README improvement","repo_path":"examples/sample-repo","model_profile":"balanced"}'
```

Dashboard flow:

1. Paste the absolute path to `examples/sample-repo`.
2. Click `Index`.
3. Click `Start`.
4. Watch Planner and Engineer create a `VerifiedPatch`.
5. Inspect changed files, checks, provenance, and unified diff.
6. Approve and apply, or reject with a reason.
7. Watch Reviewer and Documenter complete.
8. Inspect review and changelog artifacts.

## API Surface

- `POST /api/runs`: create a task run.
- `GET /api/runs/{id}`: read run state, events, steps, approvals, artifacts, verified patches, and replay records.
- `GET /api/runs/{id}/events`: stream run events through Server-Sent Events.
- `POST /api/runs/{id}/approvals/{approval_id}`: approve or reject a pending action.
- `POST /api/repos/index`: index a local repository path.
- `GET /api/search?q=...`: search indexed repository chunks.
- `GET /healthz`: health check.
- `GET /metrics`: Prometheus metrics.

Example approval:

```bash
curl -X POST http://localhost:8000/api/runs/RUN_ID/approvals/APPROVAL_ID \
  -H "Content-Type: application/json" \
  -d '{"decision":"approved","actor":"local-user"}'
```

Example rejection:

```bash
curl -X POST http://localhost:8000/api/runs/RUN_ID/approvals/APPROVAL_ID \
  -H "Content-Type: application/json" \
  -d '{"decision":"rejected","actor":"local-user","reason":"Patch scope too broad"}'
```

## Architecture

```text
Next.js Dashboard
  |
  | HTTP + SSE
  v
FastAPI API
  |
  | inline background task or Celery task
  v
LangGraph Orchestrator
  |
  +-- Planner
  +-- Engineer
  +-- Approval Gate
  +-- Reviewer
  +-- Documenter
  |
  +-- SQLite default store
  +-- Postgres optional store
  +-- Qdrant optional vector store
  +-- In-memory vector fallback
```

Important files:

- `apps/api/forgeai/api.py`: FastAPI routes and request/response flow.
- `apps/api/forgeai/core/graph.py`: LangGraph node ordering and halt/resume edges.
- `apps/api/forgeai/agents/builtins.py`: built-in MVP agents.
- `apps/api/forgeai/services/patches.py`: patch build, verification, stats, and apply helpers.
- `apps/api/forgeai/services/indexer.py`: repository chunking, indexing, and retrieval.
- `apps/api/forgeai/services/security.py`: approval policy, redaction, sensitive-path checks, and prompt-injection signals.
- `apps/api/forgeai/services/replay.py`: deterministic LLM call record helper.
- `apps/api/forgeai/plugins/base.py`: plugin contract.
- `apps/api/forgeai/db/tables.py`: persisted schema.
- `apps/web/components/forge-dashboard.tsx`: dashboard UI and interactions.
- `docs/LLM_AGENT_GUIDE.md`: future-agent operating guide.
- `docs/SECURITY_AND_VULNERABILITIES.md`: threat model and known risks.

## Data Model

Core persisted types:

- `TaskRun`: one requested engineering task.
- `RunEvent`: sequenced timeline event streamed to the dashboard.
- `AgentStep`: completed, paused, or failed agent work.
- `ToolCall`: planned or executed tool operation.
- `ApprovalRequest`: human approval gate for risky actions.
- `Artifact`: generated plan, patch, review, or docs.
- `VerifiedPatch`: evidence-backed patch with checks and apply status.
- `LLMCall`: replay metadata for model calls or deterministic stand-ins.
- `RepoChunk`: indexed source or document chunk.
- `MemoryRecord`: long-term project or run memory.
- `VisionFinding`: retained for future vision plugin work, not used by the default graph.

SQLite is the default local store. Docker can use Postgres. Qdrant is optional; tests and offline demos use the in-memory vector fallback.

## Plugin Contract

Plugins are represented by `ForgePlugin`:

```python
ForgePlugin(
    name="example",
    capabilities=("capability_name",),
    required_env=("OPTIONAL_ENV_VAR",),
    approval_policy="required",
    enabled_by_default=True,
    node_builder=lambda: graph_node,
)
```

Add new capabilities through the registry and graph. Do not bolt external tools directly into route handlers.

## Configuration

Key environment variables:

- `DATABASE_URL`: SQLite or Postgres SQLAlchemy URL.
- `REDIS_URL`: Celery broker/result backend.
- `QDRANT_URL`: Qdrant endpoint.
- `RUNNER_MODE`: `inline` or `celery`.
- `APPROVAL_MODE`: default `required`.
- `ENABLE_CLOUD_PLUGINS`: default `false`.
- `WEB_STATIC_DIR`: optional static dashboard directory served by FastAPI when present.
- `WEB_PROXY_URL`: optional internal dashboard URL proxied by FastAPI in single-container deploys.
- `NEXT_PUBLIC_API_URL`: dashboard API base URL.
- `OPENAI_API_KEY`: optional future model provider key.
- `RAILWAY_TOKEN`, `VERCEL_TOKEN`, `GITHUB_TOKEN`: optional future deploy/plugin credentials.

Default local runs must work without cloud credentials.

## Docker Compose

```bash
docker compose up --build
```

Services:

- `api`: FastAPI service on port `8000`.
- `worker`: Celery worker for Docker mode.
- `web`: Next.js dashboard on port `3000`.
- `postgres`: optional Postgres store.
- `redis`: optional Celery broker/result backend.
- `qdrant`: optional vector database.

Docker mode sets `RUNNER_MODE=celery`.

## Live Deploy

ForgeAI includes a root `Dockerfile` and `railway.json` for a single-container Railway deploy:

- FastAPI is the public process bound to `$PORT`.
- Next.js standalone server runs inside the same container on `127.0.0.1:3000`.
- FastAPI serves `/api`, `/healthz`, and `/metrics` directly, then proxies dashboard requests to internal Next.js.
- SQLite remains the default database for the hosted demo.
- `RUNNER_MODE=inline` keeps Redis optional.
- Qdrant and Postgres remain optional services for later hardening.

Deploy from the repository root:

```bash
railway up
```

Production caveat:

- Railway filesystem storage is ephemeral unless a volume or external database is configured.
- Hosted demo run history may reset on redeploy.
- Do not expose this deployment to untrusted users until API auth and workspace-root restrictions are implemented.

## Testing

Required before meaningful changes:

```bash
source .venv/bin/activate
pytest apps/api/tests
pnpm --filter @forgeai/web build
```

Useful additional checks:

```bash
source .venv/bin/activate
ruff check apps/api
pnpm --filter @forgeai/web lint
pnpm --filter @forgeai/web test:e2e
```

Current automated coverage includes:

- API run creation, approval pause, approval resume, patch apply, and completion.
- `VerifiedPatch` clean-apply evidence.
- Repository indexing and search.
- Symbol-aware chunk extraction.
- Sensitive path exclusion.
- Prompt-injection signal detection.
- Approval policy rules.
- Secret redaction helper.
- Dashboard render and mocked API submission.

## Security Model

Safe by default:

- The app runs without secrets.
- Cloud plugins are disabled unless explicitly enabled.
- Mutating tool categories are approval-required.
- Patch application pauses for approval.
- Rejections require a reason.
- Generated runtime artifacts are ignored under `.forgeai/`.
- Tests use deterministic local providers.

Known risks:

- No API authentication or authorization.
- Local path indexing can read broad local paths.
- Approval gates are application-level checks, not OS-level isolation.
- Patch application currently runs in the API/worker process, not a locked-down container.
- Secret redaction is regex-based and best-effort.
- Artifact content and local paths are visible through the API.
- Docker Compose credentials are development-only.
- No rate limits, request size limits, task quotas, or tenant isolation.

Read:

- `SECURITY.md`
- `docs/SECURITY_AND_VULNERABILITIES.md`
- `docs/LLM_AGENT_GUIDE.md`

## Roadmap

Recommended next milestones:

1. Add API authentication and ownership.
2. Add allowed workspace roots for indexing and patch application.
3. Move file and shell actions into a locked-down container sandbox.
4. Add real model provider interface with replay mode.
5. Replace deterministic hash embeddings with ONNX or transformer embeddings.
6. Add tree-sitter symbol extraction.
7. Add Playwright screenshot capture and visual review plugin.
8. Add GitHub PR plugin behind approval gates.
9. Add Railway and Vercel deploy plugins behind approval gates.
10. Add evaluation suite with seeded bugs and benchmark tasks.

## For Future LLM Agents

Start here:

1. Read `AGENTS.md`.
2. Read this README.
3. Read `docs/LLM_AGENT_GUIDE.md`.
4. Read `docs/SECURITY_AND_VULNERABILITIES.md`.
5. Inspect `apps/api/forgeai/core/graph.py` and `apps/api/forgeai/agents/builtins.py`.
6. Run `pytest apps/api/tests` and `pnpm --filter @forgeai/web build` before changing behavior.

Preserve the project principle: ForgeAI stays local-first, evidence-first, and approval-gated unless the user explicitly chooses otherwise.
