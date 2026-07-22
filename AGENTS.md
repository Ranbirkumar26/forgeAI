# ForgeAI Repo Guidance

- Keep mutating tool actions behind explicit approval paths.
- Preserve local-first behavior: the app should run without cloud credentials.
- Prefer deterministic providers and fallbacks in tests.
- Add plugin capabilities through the registry rather than hard-coding new tools into the API layer.
- Run `pytest apps/api/tests` and `pnpm --filter @forgeai/web build` before shipping meaningful changes.
- Read `README.md`, `docs/LLM_AGENT_GUIDE.md`, and `docs/SECURITY_AND_VULNERABILITIES.md` before large changes.
- Update vulnerability notes whenever adding file, shell, browser, git, deploy, auth, or cloud-provider behavior.
- Never commit `.env`, runtime artifacts, generated screenshots, local DBs, virtualenvs, or dependency folders.
