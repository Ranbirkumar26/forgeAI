# ForgeAI Repo Guidance

- Keep mutating tool actions behind explicit approval paths.
- Preserve local-first behavior: the app should run without cloud credentials.
- Prefer deterministic providers and fallbacks in tests.
- Add plugin capabilities through the registry rather than hard-coding new tools into the API layer.
- Run `pytest apps/api/tests` and `pnpm --filter @forgeai/web build` before shipping meaningful changes.
- Read `README.md`, `docs/LLM_AGENT_GUIDE.md`, and `docs/SECURITY_AND_VULNERABILITIES.md` before large changes.
- Update vulnerability notes whenever adding file, shell, browser, git, deploy, auth, or cloud-provider behavior.
- Never commit `.env`, runtime artifacts, generated screenshots, local DBs, virtualenvs, or dependency folders.

## Decision Log

- 2026-07-31: Refocused MVP around `VerifiedPatch` instead of many low-evidence agents. Reason: recruiter demo value comes from evidence-backed patch approval, not agent count.
- 2026-07-31: Collapsed default graph to Planner, Engineer, Reviewer, and Documenter. Reason: simpler trace, fewer low-evidence stages, easier test surface.
- 2026-07-31: Kept SQLite and inline runner as default. Reason: local-first demo should run without Redis, Postgres, Qdrant, or cloud credentials.
- 2026-07-31: Added local `git apply --check` verification and approved `git apply` mutation. Reason: MVP now proves patch apply path, while security docs call out missing container sandbox.
- 2026-07-31: Kept deterministic hash embeddings as default fallback. Reason: tests and demo must not require paid APIs or model downloads.
- 2026-07-31: Updated dashboard to run trace, diff, approval, and checks view. Reason: v2 brief asked for CI-style evidence view instead of chatbot or dark operations UI.

## Deferred Features

- "Locked-down container sandbox for file, shell, browser, git, and deploy actions."
- "Ephemeral git worktree inside locked-down container. Network none default, egress allowlist only dependency install."
- "Tree-sitter symbol index."
- "Local code-aware ONNX embeddings; hash only benchmark baseline."
- "Replay and offline demo with LLMCall records."
- "Eval: seeded bugs plus SWE-bench Lite, EVALUATION.md."
- "Vision: Playwright screenshots, OpenCV diff/layout checks, OCR-friendly artifact storage, and model-based screenshot review."
- "GitHub PR creation, git push, Railway deploy, Vercel deploy, Supabase cloud setup, and browser-form automation."
- "API authentication, ownership, quotas, rate limits, request size limits, and production CORS controls."
- "Budget manager and circuit breaker for model/tool calls."
