# Security Policy

ForgeAI is an MVP/demo project, not a hardened production service. Treat it as a local developer tool unless and until the hardening items below are implemented.

## Supported Security Posture

Current intended use:

- Run locally on a trusted machine.
- Use test/sample repositories or repositories you are allowed to inspect.
- Keep cloud/deploy plugins disabled unless you intentionally configure credentials.
- Review and approve all mutating actions before execution.

Not yet supported:

- Internet-exposed API deployment.
- Multi-user or multi-tenant usage.
- Untrusted repository execution.
- Untrusted browser automation.
- Fully autonomous deploy/push/PR workflows.

## Known Vulnerabilities and Risks

| Area | Current risk | Required hardening |
| --- | --- | --- |
| API access | No authentication or authorization. Anyone who can reach the API can create runs, read artifacts, approve actions, and index paths. | Add auth, sessions/JWT validation, per-user ownership checks, and audit logs. |
| Local file access | `/api/repos/index` accepts a path and indexes readable files under it. | Restrict indexing to configured workspace roots and reject symlinks/out-of-root paths. |
| Approval enforcement | Approval gates are application-level state checks. They are not an OS sandbox. | Run file/shell/browser/deploy tools in a constrained worker sandbox. |
| Secrets | Redaction is regex-based and best-effort. | Add structured secret scanning, deny-list checks, and avoid storing sensitive content by default. |
| Artifacts | Artifact contents and paths are persisted and returned by the API. | Add access control, retention policy, and path/content minimization. |
| CORS | Local dev origins are allowed by default. | Tighten CORS per deployment environment. |
| Docker credentials | Compose uses simple development database credentials. | Use secret management and environment-specific credentials. |
| Rate limits | No API rate limiting or body size policy. | Add request limits, task quotas, and worker queue controls. |
| Cloud plugins | Deployment/GitHub/browser plugins are represented as contracts, not hardened integrations. | Implement provider-specific permission checks, dry-runs, and explicit approval flows. |

## Reporting Security Issues

This is currently a personal/demo repository. If you find a vulnerability:

1. Open a private issue or contact the maintainer directly if possible.
2. Include affected endpoint/file, reproduction steps, and impact.
3. Do not include real secrets in reports.

## Security Rules for Contributors and Agents

- Do not remove approval gates for mutating tools.
- Do not require cloud credentials for local tests.
- Do not commit `.env`, `.forgeai/`, `.venv/`, `node_modules/`, or generated build output.
- Do not expose `service_role`, deploy, GitHub, OpenAI, Railway, Vercel, or database admin tokens to frontend code.
- Keep `NEXT_PUBLIC_*` values non-secret.
- Prefer deterministic fake providers in tests.
- Add tests for any new security-sensitive behavior.
