# Security and Vulnerability Notes

This document is intentionally direct. It helps humans and LLM agents understand where ForgeAI is safe, where it is only simulated, and where it is vulnerable.

## Trust Boundaries

ForgeAI has these trust boundaries:

- Browser/dashboard to FastAPI API.
- API to database and artifact store.
- API/worker to local filesystem.
- API/worker to Qdrant or in-memory vector store.
- API to Redis/Celery in Docker mode.
- Future plugins to GitHub, Railway, Vercel, Supabase, browsers, and model providers.

The most sensitive boundary is API/worker to local filesystem. Any future feature that reads, writes, executes, deploys, opens browsers, or pushes git state must be treated as high risk.

## Current Safety Controls

- `ApprovalPolicy` marks mutating tool categories as approval-required.
- `coder` prepares a patch artifact and requests approval for `file_write`.
- `approval-gate` halts the LangGraph run when an approval is pending.
- `deployment` skips cloud deploys unless `ENABLE_CLOUD_PLUGINS=true`.
- `redact_secrets` removes common token/password patterns from events and artifacts.
- `.gitignore` excludes `.env`, `.venv`, `.forgeai`, `node_modules`, `.next`, and test/build output.
- Tests use deterministic hash embeddings and in-memory vector fallback when Qdrant is unavailable.

## Known Vulnerabilities

### 1. No API Authentication

Risk:

- Anyone with network access to the API can create runs, read run data, approve actions, index paths, and search indexed chunks.

Impact:

- Sensitive source code or generated artifacts could be exposed.
- A malicious caller could approve actions once real mutating tools are implemented.

Fix:

- Add authentication middleware.
- Add user/project ownership to `TaskRun`, `ApprovalRequest`, `Artifact`, `RepoChunk`, and `MemoryRecord`.
- Require authorization checks on every API endpoint.

### 2. Repository Indexing Can Read Broad Local Paths

Risk:

- `/api/repos/index` accepts a caller-provided path and walks it with `Path.rglob`.

Impact:

- If the API is exposed, a caller could request indexing of sensitive readable directories.

Fix:

- Add `ALLOWED_WORKSPACE_ROOTS`.
- Resolve paths and reject anything outside allowed roots.
- Reject or carefully resolve symlinks.
- Add max file count, max bytes, and timeout limits.

### 3. Approval Gates Are Not a Sandbox

Risk:

- Approval state is enforced in application logic, not by a kernel/container sandbox.

Impact:

- A bug in graph routing or future tool code could bypass approval.

Fix:

- Execute mutating tools in a separate constrained worker.
- Enforce allowlists at the tool-runner layer.
- Require approval IDs/tokens to execute mutating calls.
- Add tests proving unapproved tools cannot execute.

### 4. Secret Redaction Is Best-Effort

Risk:

- Regex redaction can miss unusual secret formats or secrets split across strings.

Impact:

- Secrets could be persisted into events or artifacts.

Fix:

- Add structured secret scanners.
- Redact before persistence and before API response.
- Avoid storing raw command output by default.
- Add tests for provider-specific token formats.

### 5. Artifact API Exposes Paths and Contents

Risk:

- Artifact records include content and local paths.

Impact:

- Callers can learn local filesystem structure and see generated sensitive content.

Fix:

- Add auth.
- Store relative artifact paths.
- Add artifact retention and deletion.
- Add content classification before persistence.

### 6. Development CORS Defaults

Risk:

- Localhost and 127.0.0.1 dev origins are allowed.

Impact:

- Fine for local demo; risky if reused in production.

Fix:

- Make production CORS explicit and narrow.
- Fail startup in production if permissive dev origins are configured.

### 7. Docker Compose Credentials Are Development-Only

Risk:

- Postgres credentials are hard-coded as `forgeai/forgeai`.

Impact:

- Unsafe for shared or public deployments.

Fix:

- Use secret management and environment-specific credentials.
- Never expose Postgres, Redis, or Qdrant publicly without auth/network controls.

### 8. No Rate Limits or Quotas

Risk:

- Callers can create many runs, index large repos, and stream events.

Impact:

- CPU, memory, disk, DB, and queue exhaustion.

Fix:

- Add request body limits, file limits, task quotas, rate limiting, and queue backpressure.

### 9. Cloud Plugins Are Not Hardened Yet

Risk:

- Deployment/GitHub/browser integrations are represented as plugin contracts and graph nodes, not finished secure integrations.

Impact:

- A future naive implementation could push code, deploy, or fill browser forms without adequate checks.

Fix:

- Implement dry-run previews.
- Require approval per provider action.
- Record exact target repo/project/environment.
- Verify post-action state.
- Add provider-specific least-privilege token guidance.

## Security Invariants to Preserve

- The default demo must work without secrets.
- Any mutating action must create a visible approval request first.
- Tests must not need real cloud/model credentials.
- Cloud deploy plugins must remain disabled by default.
- Frontend code must never receive server-only tokens.
- Runtime artifacts must stay ignored by git.

## Recommended Hardening Order

1. API authentication and ownership model.
2. Allowed workspace roots for indexing.
3. Sandboxed tool runner for file/shell/browser/git/deploy actions.
4. Stronger secret scanning and output minimization.
5. Production CORS/env validation.
6. Rate limits and task quotas.
7. Provider-specific GitHub/Railway/Vercel approval flows.
8. Audit log export and tamper-resistant run history.
