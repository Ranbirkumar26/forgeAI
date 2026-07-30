# LLM Agent Guide

Read this before changing ForgeAI.

## Product Contract

ForgeAI is not a chatbot. It is a local-first control plane for verified software changes.

The core unit of value is `VerifiedPatch`:

- unified diff
- base SHA
- changed files
- line counts
- clean-apply check
- secret-scan check
- approval record
- apply status
- provenance
- replay metadata

Do not add behavior that produces plans or prose without evidence.

## Required Reading Order

1. `AGENTS.md`
2. `README.md`
3. `docs/SECURITY_AND_VULNERABILITIES.md`
4. `apps/api/forgeai/core/graph.py`
5. `apps/api/forgeai/agents/builtins.py`
6. `apps/api/forgeai/services/patches.py`
7. `apps/api/forgeai/services/security.py`

## Current Graph

```text
planner -> engineer -> approval-gate
  -> reviewer -> documenter
```

Node responsibilities:

- `planner`: creates verified patch work order and replay metadata.
- `engineer`: retrieves context, builds patch, verifies clean apply, requests approval, applies approved patch.
- `approval-gate`: halts while any approval is pending.
- `reviewer`: audits tool calls, checks, approvals, and suspicious retrieved context.
- `documenter`: writes changelog artifact and stores memory summary.

Do not reintroduce many single-purpose default agents unless they produce durable evidence and tests. Vision, deployment, GitHub, browser, and cloud actions belong behind disabled plugins until hardened.

## Backend Navigation

- `apps/api/forgeai/api.py`: API routes.
- `apps/api/forgeai/core/graph.py`: LangGraph flow.
- `apps/api/forgeai/core/runner.py`: run execution and resume behavior.
- `apps/api/forgeai/agents/builtins.py`: built-in agent nodes.
- `apps/api/forgeai/services/events.py`: event, artifact, approval, and tool-call persistence.
- `apps/api/forgeai/services/patches.py`: patch build, verify, stats, and apply.
- `apps/api/forgeai/services/security.py`: approval policy, redaction, sensitive paths, prompt-injection signals.
- `apps/api/forgeai/services/indexer.py`: repository indexing and retrieval.
- `apps/api/forgeai/services/vector_store.py`: Qdrant and in-memory search.
- `apps/api/forgeai/services/replay.py`: LLM call replay records.
- `apps/api/forgeai/db/tables.py`: persisted schema.

## Frontend Navigation

- `apps/web/components/forge-dashboard.tsx`: main dashboard.
- `apps/web/lib/api.ts`: API client and TypeScript types.
- `apps/web/app/globals.css`: UI styling.

The dashboard should stay dense and evidence-first:

- run trace
- status
- approval evidence
- checks
- unified diff
- artifacts
- vector search
- token and event counters

Avoid marketing UI, dark operations styling, gradients, robot icons, and chat-first layouts.

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

## How Approval Works

Mutating tools must:

1. Create `ToolCall`.
2. Create `ApprovalRequest`.
3. Halt graph at `approval-gate`.
4. Resume only after approved status.
5. Record action output and status.

Current patch approvals use `action_type="apply_patch"`.

Rejected approvals must include a reason.

Do not execute file writes, shell mutations, git pushes, deploys, browser form actions, or PR creation before approval.

## How Retrieval Works

Indexing does:

- skip dependency/build/cache folders
- respect `.forgeignore`
- skip sensitive file names
- cap file size
- skip files with likely secrets
- extract lightweight symbols for Python, TypeScript, and JavaScript
- store line ranges, imports, signatures, and docstrings
- embed chunks with deterministic local hash embeddings
- use Qdrant when available and in-memory fallback otherwise

Retrieval priority:

1. keyword and symbol match
2. vector fallback

Tree-sitter and transformer embeddings are deferred.

## How to Add a New Agent

1. Add node function under `apps/api/forgeai/agents` or a plugin package.
2. Register it with `ForgePlugin`.
3. Add graph edges in `apps/api/forgeai/core/graph.py`.
4. Persist evidence as `RunEvent`, `AgentStep`, `ToolCall`, `ApprovalRequest`, `Artifact`, or `VerifiedPatch`.
5. Add tests for normal behavior, approval behavior, and failure behavior.
6. Update README, this guide, and vulnerability notes if behavior changes.

## How to Add a New Tool

Before coding:

- classify read-only or mutating
- identify credentials touched
- identify local files touched
- identify network targets
- define approval action type
- define artifact or event evidence
- define deterministic test double
- update vulnerability notes

Mutating tools must be gated by `ApprovalPolicy`.

## Security Checklist

For every change, answer:

- Can unauthenticated callers trigger it?
- Can it read arbitrary local files?
- Can it write files or run commands?
- Can it leak secrets through events, artifacts, logs, screenshots, or frontend state?
- Does it call cloud services?
- Does it need quotas or timeouts?
- Does it change approval boundaries?
- Does it require updates to security docs?

## Do Not

- Do not put secrets in `NEXT_PUBLIC_*`.
- Do not call real LLMs, cloud APIs, deploy providers, or browsers from tests.
- Do not make Docker or cloud services required for the default demo.
- Do not bypass `ApprovalPolicy`.
- Do not add shell, git, browser, deploy, or PR actions without approval and vulnerability docs.
- Do not remove the in-memory vector fallback.
- Do not convert the dashboard into chat.
- Do not store unredacted command output.

## High-Value Next Work

1. API authentication and ownership.
2. Allowed workspace roots.
3. Container sandbox for mutating actions.
4. Real replayable model-provider interface.
5. ONNX or transformer embeddings.
6. Tree-sitter symbol index.
7. Playwright screenshot and visual review plugin.
8. GitHub PR plugin with dry-run and approval.
9. Evaluation suite with seeded bugs.
