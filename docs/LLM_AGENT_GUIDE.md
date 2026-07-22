# LLM Agent Guide

This guide is for future coding agents working on ForgeAI. Read it before making changes.

## Mission

ForgeAI is a local-first autonomous software engineering platform. The product should feel like a small version of Claude Code/Devin/Cursor-style orchestration, but with explicit approval gates and visible run telemetry.

Do not turn it into a plain chatbot.

## Core Principles

- Local-first: the default demo must run without cloud credentials.
- Approval-gated: file writes, shell mutations, git pushes, browser form actions, PRs, and deployments must require approval.
- Plugin-oriented: add agents/tools through the plugin registry and graph, not as route-handler one-offs.
- Deterministic tests: tests should not call external LLMs, cloud APIs, or real deploy providers.
- Security-aware: document new risks when adding powerful tools.

## Fast Navigation

Backend:

- `apps/api/forgeai/api.py`: API routes.
- `apps/api/forgeai/core/graph.py`: LangGraph flow.
- `apps/api/forgeai/core/runner.py`: run execution and resume behavior.
- `apps/api/forgeai/agents/builtins.py`: built-in agent nodes.
- `apps/api/forgeai/services/events.py`: event, artifact, approval, and tool-call persistence.
- `apps/api/forgeai/services/security.py`: approval policy and redaction.
- `apps/api/forgeai/services/indexer.py`: repository indexing.
- `apps/api/forgeai/services/vector_store.py`: Qdrant/in-memory search.
- `apps/api/forgeai/db/tables.py`: persisted schema.

Frontend:

- `apps/web/components/forge-dashboard.tsx`: main dashboard.
- `apps/web/lib/api.ts`: frontend API client and TypeScript types.
- `apps/web/app/globals.css`: responsive UI styling.

Ops/docs:

- `docker-compose.yml`: local full stack.
- `.github/workflows/ci.yml`: CI.
- `docs/ARCHITECTURE.md`: system overview.
- `docs/SECURITY_AND_VULNERABILITIES.md`: threat model and known risks.
- `SECURITY.md`: public security policy.

## Run Commands

Install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e "apps/api[dev]"
pnpm install
```

Backend:

```bash
source .venv/bin/activate
uvicorn forgeai.main:app --app-dir apps/api --reload
```

Frontend:

```bash
pnpm dev
```

Required verification:

```bash
source .venv/bin/activate
pytest apps/api/tests
pnpm --filter @forgeai/web build
```

Extra verification:

```bash
source .venv/bin/activate
ruff check apps/api
pnpm --filter @forgeai/web lint
pnpm --filter @forgeai/web test:e2e
```

## How a Run Works

`POST /api/runs` creates a `TaskRun`, emits an event, and dispatches execution.

Execution goes through:

```text
planner -> repo-rag -> coder -> approval-gate
  -> testing -> vision -> security -> review -> docs -> deployment -> memory
```

If there is a pending approval, the graph halts and the run status becomes `awaiting_approval`. `POST /api/runs/{id}/approvals/{approval_id}` resolves the approval and resumes the run.

## How to Add a New Agent

1. Add the node function in a suitable module under `apps/api/forgeai/agents` or a new plugin package.
2. Register it with `ForgePlugin` in the plugin registry.
3. Add graph edges in `apps/api/forgeai/core/graph.py`.
4. Persist important actions as `RunEvent`, `AgentStep`, `ToolCall`, `ApprovalRequest`, or `Artifact`.
5. Add tests for normal behavior and approval/security behavior.
6. Update this guide and the README if the public behavior changes.

## How to Add a New Tool

Before adding a tool, decide:

- Is it read-only or mutating?
- Does it touch local files, shell, browser, git, cloud, credentials, or user accounts?
- What exact approval action type should gate it?
- What artifact/log should prove what happened?
- What deterministic fake can tests use?

Mutating tools should create a `ToolCall` and an `ApprovalRequest` before executing.

## Security Checklist for Changes

For every change, ask:

- Can an unauthenticated caller trigger this over HTTP?
- Can the change read arbitrary local files?
- Can it write files or run commands?
- Can it leak secrets through events, artifacts, logs, screenshots, or frontend state?
- Does it require cloud credentials?
- Does it preserve deterministic tests?
- Does it need a new known-risk note?

## Do Not Do This

- Do not put secrets in `NEXT_PUBLIC_*`.
- Do not call real LLM/cloud APIs from tests.
- Do not make Docker/cloud services required for the default local demo.
- Do not bypass `ApprovalPolicy` for convenience.
- Do not add deployment, GitHub push, browser form, or shell execution without an approval gate.
- Do not delete the in-memory vector fallback; it is useful for tests and offline demos.

## Good First Future Improvements

- Convert FastAPI startup to lifespan handlers.
- Replace `datetime.utcnow()` with timezone-aware UTC helpers.
- Add API authentication.
- Add workspace-root validation for repository indexing.
- Add real sandboxed patch application.
- Add richer Playwright screenshot capture.
- Add provider interfaces for real LLM and embedding calls.
- Add GitHub PR plugin with dry-run and approval flow.
