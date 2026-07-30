# Security and Vulnerability Notes

This document exists so humans and future LLM agents understand exactly where ForgeAI is safe, where it is only partially hardened, and where it is vulnerable.

## Trust Boundaries

- Browser dashboard to FastAPI API.
- API to database and artifact store.
- API or worker to local filesystem.
- API or worker to local git repository.
- API to Qdrant or in-memory vector store.
- API to Redis and Celery in Docker mode.
- Future plugins to GitHub, Railway, Vercel, Supabase, browsers, and model providers.

Highest-risk boundary: API or worker to local filesystem and git repository.

Any feature that reads files, writes files, runs commands, deploys, opens browsers, pushes git state, or touches credentials is high risk.

## Current Safety Controls

- `ApprovalPolicy` marks mutating tool categories as approval-required.
- `engineer` creates `VerifiedPatch` and requests approval before `git apply`.
- `approval-gate` halts the graph when approvals are pending.
- Rejected approvals require a reason.
- `VerifiedPatch` records diff, base SHA, files changed, line counts, clean-apply check, secret-scan check, provenance, and apply status.
- Repository indexing skips sensitive paths, large files, ignored folders, `.forgeignore` matches, and files with likely secrets.
- Retrieved context is scanned for prompt-injection signals.
- `redact_secrets` removes common token/password patterns from persisted messages and artifacts.
- Cloud deploy plugins remain disabled unless credentials and settings are explicitly configured.
- Tests use deterministic local providers and do not require external credentials.
- Runtime artifacts are ignored by git under `.forgeai/`.

## Known Vulnerabilities

### 1. No API Authentication

Risk:

- Anyone with network access to the API can create runs, read run data, approve actions, index paths, search chunks, and apply approved patches.

Impact:

- Sensitive code or artifacts could be exposed.
- A malicious caller could approve local file mutations.

Fix:

- Add authentication middleware.
- Add user and project ownership columns.
- Require authorization checks on every endpoint.
- Separate local demo auth from production auth.

### 2. Repository Indexing Can Read Broad Local Paths

Risk:

- `/api/repos/index` accepts caller-provided paths and walks them.

Impact:

- If exposed, caller could index sensitive readable directories.

Current mitigation:

- Sensitive names and large files are skipped.
- Files with likely secrets are skipped.
- `.forgeignore` is supported.

Remaining fix:

- Add `ALLOWED_WORKSPACE_ROOTS`.
- Resolve paths and reject anything outside allowed roots.
- Reject symlinks or resolve them safely.
- Add max file count, max total bytes, and timeout limits.

### 3. Patch Application Is Not Sandboxed

Risk:

- Approved patch application runs `git apply` from the API or worker process.

Impact:

- A bug in patch generation, approval routing, or path handling could mutate files outside intended scope.

Current mitigation:

- Patch application requires approval.
- `git apply --check` runs before approval.
- Diff secret scan must pass.
- Patch evidence is stored in `VerifiedPatch`.

Remaining fix:

- Apply patches inside ephemeral git worktrees.
- Run tool execution in a locked-down container.
- Disable network by default.
- Add egress allowlists for dependency install only.
- Require approval token to execute every mutating tool call.
- Add tests proving unapproved tools cannot execute.

### 4. Approval Gates Are Application Logic

Risk:

- Approval state is enforced in Python graph and service code, not by OS policy.

Impact:

- Future tool code could bypass approvals accidentally.

Fix:

- Centralize mutating tool execution behind one tool runner.
- Make tool runner require approval ID and approved status.
- Deny direct subprocess or file write calls in agent nodes.
- Add static checks for forbidden direct tool use.

### 5. Secret Redaction Is Best-Effort

Risk:

- Regex redaction can miss uncommon secret formats, multiline secrets, or split secrets.

Impact:

- Secrets could be stored in events, artifacts, logs, patches, or frontend state.

Current mitigation:

- Common API key, token, password, GitHub token, OpenAI-style key, and private-key patterns are redacted.
- Indexer skips likely secret files and likely secret content.

Remaining fix:

- Add structured secret scanners.
- Redact before persistence and before API response.
- Store command output tails only.
- Add provider-specific token tests.

### 6. Artifact API Exposes Paths and Contents

Risk:

- Artifact records include content and local artifact paths.

Impact:

- Caller can learn local filesystem structure and generated content.

Fix:

- Add auth and authorization.
- Store relative artifact paths.
- Add artifact retention and deletion.
- Classify artifacts before persistence.

### 7. Prompt Injection In Retrieved Files

Risk:

- Indexed repository files can contain instructions aimed at the agent.

Impact:

- Future real LLM calls could follow malicious repo content.

Current mitigation:

- Retrieved context is scanned for known prompt-injection signals.
- Findings are surfaced to reviewer events.

Remaining fix:

- Wrap retrieved context as untrusted data in model prompts.
- Add policy tests for prompt injection fixtures.
- Make model providers enforce system/developer instruction hierarchy.

### 8. Development CORS Defaults

Risk:

- Localhost and 127.0.0.1 dev origins are allowed.

Impact:

- Safe for local demo, unsafe if reused in production.

Fix:

- Make production CORS explicit.
- Fail startup in production when dev origins are configured.

### 9. Docker Compose Credentials Are Development-Only

Risk:

- Compose uses simple local credentials.

Impact:

- Unsafe for shared or public deployments.

Fix:

- Use environment-specific credentials and platform secrets.
- Do not expose Postgres, Redis, or Qdrant publicly without auth and network controls.

### 10. No Rate Limits or Quotas

Risk:

- Callers can create many runs, index large repos, stream events, and generate artifacts.

Impact:

- CPU, memory, disk, database, and queue exhaustion.

Fix:

- Add request body limits.
- Add task quotas.
- Add rate limiting.
- Add queue backpressure.
- Add artifact retention.

### 11. Cloud Plugins Are Not Hardened

Risk:

- GitHub, deploy, browser, and cloud-provider integrations are only plugin contracts or deferred work.

Impact:

- Future naive implementation could push code, deploy, or fill browser forms without adequate controls.

Fix:

- Implement dry-run previews.
- Require approval per provider action.
- Record exact target repo, project, branch, environment, URL, and account.
- Verify post-action state.
- Document least-privilege token scopes.

## Security Invariants

- Default demo must work without secrets.
- Any mutating action must create a visible approval request first.
- Rejected approvals must include a reason.
- Tests must not need real cloud, browser, deploy, or model credentials.
- Cloud deploy plugins remain disabled by default.
- Frontend code must never receive server-only tokens.
- Runtime artifacts stay ignored by git.
- Vulnerability notes must be updated when adding file, shell, browser, git, deploy, auth, or cloud behavior.

## Hardening Order

1. API authentication and ownership model.
2. Allowed workspace roots for indexing and patch application.
3. Sandboxed tool runner for file, shell, browser, git, and deploy actions.
4. Stronger secret scanning and output minimization.
5. Prompt-injection policy tests.
6. Production CORS and environment validation.
7. Rate limits and task quotas.
8. Provider-specific GitHub, Railway, Vercel, and Supabase approval flows.
9. Audit log export and tamper-resistant run history.
