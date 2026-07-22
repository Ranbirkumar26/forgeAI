# ForgeAI

ForgeAI is a local-first autonomous AI software engineering control plane. It is designed to look and behave like the skeleton of a real developer co-pilot: it indexes a repository, plans work, prepares code changes, pauses at approval gates, runs safe checks, generates visual review artifacts, records memory, and exposes the whole run through a live dashboard.

This is not another chatbot. The core product idea is an approval-gated autonomous software engineer with:

- FastAPI API for orchestration, approvals, repository indexing, search, metrics, and SSE events.
- LangGraph execution graph for multi-agent task flow.
- Plugin registry for adding agents and tools without rewriting the API layer.
- Next.js dashboard for live graph state, timeline, approvals, artifacts, vector search, and usage counters.
- Local-first RAG with deterministic embeddings, Qdrant when available, and in-memory fallback for tests/offline demos.
- OpenCV visual diff generation for UI review artifacts.
- Celery/Redis worker path for Docker mode, plus inline mode for simple local development.
- Postgres/pgvector-ready Docker stack while keeping SQLite as the default zero-cloud path.
- Explicit security documentation for known weaknesses and hardening priorities.

## Repository Status

ForgeAI is an MVP scaffold intended for demos, recruiter review, and future agent-driven extension. It already runs end-to-end locally, but it is not production-hardened yet.

Current behavior:

- A task run starts from the dashboard or API.
- Planner and Repo RAG agents create an execution context.
- Coder prepares a patch artifact and pauses for approval before any write-like action.
- After approval, the graph continues through Testing, Vision, Security, Review, Documentation, Deployment, and Memory agents.
- Deployment is intentionally skipped unless cloud plugins and credentials are explicitly enabled.

Important limitation:

- The current Coder Agent prepares a demo patch artifact. It does not yet apply patches to arbitrary repositories. That is deliberate for the first approval-gated MVP.

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

If ports are busy, use alternates:

```bash
uvicorn forgeai.main:app --app-dir apps/api --host 127.0.0.1 --port 8002 --reload
NEXT_PUBLIC_API_URL=http://127.0.0.1:8002 pnpm --dir apps/web exec next dev --hostname 127.0.0.1 --port 3002
```

## Docker Compose

```bash
docker compose up --build
```

Services:

- `api`: FastAPI service on port `8000`
- `worker`: Celery worker
- `web`: Next.js dashboard on port `3000`
- `postgres`: pgvector-ready Postgres
- `redis`: Celery broker/result backend
- `qdrant`: vector database

Docker mode sets `RUNNER_MODE=celery`, so runs are executed by the worker instead of FastAPI background tasks.

## Demo Script

Use the included sample repository:

```bash
curl -X POST http://localhost:8000/api/repos/index \
  -H "Content-Type: application/json" \
  -d '{"path":"examples/sample-repo"}'
```

Then open the dashboard and:

1. Paste or keep the sample repo path.
2. Click `Index Repo`.
3. Click `Start Run`.
4. Watch Planner, Repo RAG, and Coder run.
5. Approve the prepared patch.
6. Watch Testing, Vision, Security, Review, Docs, Deployment, and Memory complete.
7. Inspect generated artifacts: execution plan, patch, test report, visual diff, review notes, changelog, and LinkedIn draft.

## API Surface

Core endpoints:

- `POST /api/runs`: create a task run.
- `GET /api/runs/{id}`: read run state, steps, approvals, events, and artifacts.
- `GET /api/runs/{id}/events`: stream run events via Server-Sent Events.
- `POST /api/runs/{id}/approvals/{approval_id}`: approve or reject a pending action.
- `POST /api/repos/index`: chunk and index a local repository path.
- `GET /api/search?q=...`: semantic search over indexed repository chunks.
- `GET /healthz`: health check.
- `GET /metrics`: Prometheus metrics.

Example run:

```bash
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{"task":"Prepare a safe README improvement","model_profile":"balanced"}'
```

Example approval:

```bash
curl -X POST http://localhost:8000/api/runs/RUN_ID/approvals/APPROVAL_ID \
  -H "Content-Type: application/json" \
  -d '{"decision":"approved","actor":"local-user"}'
```

## Architecture

```text
Dashboard
  |
  | HTTP + SSE
  v
FastAPI API
  |
  | inline background task or Celery task
  v
LangGraph Orchestrator
  |
  +-- Planner Agent
  +-- Repo RAG Agent
  +-- Coder Agent
  +-- Approval Gate
  +-- Testing Agent
  +-- Vision Agent
  +-- Security Agent
  +-- Review Agent
  +-- Documentation Agent
  +-- Deployment Agent
  +-- Memory Agent
  |
  +-- SQLite/Postgres: runs, events, approvals, artifacts, memory
  +-- Qdrant/in-memory: repository vector search
  +-- Redis: Celery broker/result backend in Docker mode
```

Important files:

- `apps/api/forgeai/api.py`: FastAPI routes and request/response flow.
- `apps/api/forgeai/core/graph.py`: LangGraph node ordering and halt/resume edges.
- `apps/api/forgeai/agents/builtins.py`: built-in MVP agents.
- `apps/api/forgeai/plugins/base.py`: plugin contract.
- `apps/api/forgeai/plugins/registry.py`: plugin registration.
- `apps/api/forgeai/services/security.py`: approval policy and redaction helpers.
- `apps/api/forgeai/services/indexer.py`: repository chunking and indexing.
- `apps/api/forgeai/services/vector_store.py`: Qdrant and in-memory vector stores.
- `apps/web/components/forge-dashboard.tsx`: dashboard UI and interactions.

## Agent Flow

1. `planner`: decomposes the task and creates the execution plan artifact.
2. `repo-rag`: retrieves indexed chunks related to the task.
3. `coder`: prepares a patch artifact and requests approval for `file_write`.
4. `approval-gate`: halts when any approval is pending.
5. `testing`: records safe test commands and creates a test report artifact.
6. `vision`: creates an OpenCV before/after diff artifact.
7. `security`: reviews tool calls and approval requirements.
8. `review`: generates risk-focused review notes.
9. `docs`: creates changelog and LinkedIn draft artifacts.
10. `deployment`: skips cloud deploy unless explicitly enabled.
11. `memory`: stores the run summary as long-term project memory.

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

Add new capabilities through the registry in `apps/api/forgeai/plugins`, then wire nodes through the graph. Avoid hard-coding new external tools directly into route handlers.

## Data Model

Core persisted types:

- `TaskRun`: one requested engineering task.
- `RunEvent`: timeline event streamed to the dashboard.
- `AgentStep`: completed or paused agent work.
- `ToolCall`: planned or executed tool operation.
- `ApprovalRequest`: human approval gate for risky actions.
- `Artifact`: generated plan, patch, report, screenshot diff, review, or docs.
- `RepoChunk`: indexed source/document chunk.
- `MemoryRecord`: long-term project/user memory.
- `VisionFinding`: image/layout review finding.

The database tables live in `apps/api/forgeai/db/tables.py`. SQLite is the default local store; Docker uses Postgres.

## Configuration

Key environment variables:

- `DATABASE_URL`: SQLite or Postgres SQLAlchemy URL.
- `REDIS_URL`: Celery broker/result backend.
- `QDRANT_URL`: Qdrant endpoint.
- `RUNNER_MODE`: `inline` or `celery`.
- `APPROVAL_MODE`: default `required`.
- `ENABLE_CLOUD_PLUGINS`: default `false`.
- `NEXT_PUBLIC_API_URL`: dashboard API base URL.
- `OPENAI_API_KEY`: optional future model provider key.
- `RAILWAY_TOKEN`, `VERCEL_TOKEN`, `GITHUB_TOKEN`: optional future deploy/plugin credentials.

The app should run without cloud credentials. Do not make cloud services required for tests or the default local demo.

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

- API run creation, approval pause, approval resume, and completion.
- Repository indexing and semantic search.
- Approval policy rules.
- Secret redaction helper.
- Vision diff artifact creation.
- Dashboard render and mocked API submission.

## Security Model

ForgeAI is intentionally approval-gated, but it is not a sandbox yet.

Safe by default:

- Cloud deploy plugins are disabled unless `ENABLE_CLOUD_PLUGINS=true`.
- Mutating tool categories are modeled as approval-required.
- The Coder Agent currently prepares patch artifacts instead of applying them.
- Tests use deterministic local providers and do not need external credentials.
- Generated runtime artifacts are ignored under `.forgeai/`.

Known vulnerabilities and hardening priorities:

- No authentication or authorization on the API.
- Local path indexing can read any path reachable by the process.
- Approval gates are application-level checks, not OS-level isolation.
- CORS is configured for local development origins.
- Artifact content and file paths are visible through the API to any caller with network access.
- Secret redaction is regex-based and can miss unusual credential formats.
- Docker Compose uses development credentials.
- No rate limiting, request size limits, or tenant isolation.
- Qdrant fallback is in-memory and process-local.
- Deployment/GitHub/browser automation plugins are contracts, not hardened implementations.

Read the dedicated security notes before adding real code execution or cloud deployment:

- `SECURITY.md`
- `docs/SECURITY_AND_VULNERABILITIES.md`
- `docs/LLM_AGENT_GUIDE.md`

## Roadmap

Recommended next milestones:

1. Add authentication for dashboard and API.
2. Add a real patch-application worker that runs in a sandboxed checkout.
3. Restrict repository indexing to configured workspace roots.
4. Add OS/process sandboxing for shell and file tools.
5. Add model provider abstraction for OpenAI/Anthropic/local models.
6. Add GitHub PR creation behind approval gates.
7. Add Railway/Vercel deployment plugins behind approval gates.
8. Add Supabase-compatible migrations and optional cloud Postgres setup.
9. Add richer visual inspection with real Playwright screenshots.
10. Add task-quality telemetry and ML prediction features.

## For Future LLM Agents

Start here:

1. Read `AGENTS.md`.
2. Read this README.
3. Read `docs/LLM_AGENT_GUIDE.md`.
4. Read `docs/SECURITY_AND_VULNERABILITIES.md`.
5. Inspect `apps/api/forgeai/core/graph.py` and `apps/api/forgeai/agents/builtins.py`.
6. Run `pytest apps/api/tests` and `pnpm --filter @forgeai/web build` before changing behavior.

Preserve the project principle: ForgeAI should remain local-first and approval-gated unless the user explicitly chooses otherwise.
