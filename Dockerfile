FROM node:22-slim AS web-build

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --filter @forgeai/web --frozen-lockfile

COPY apps/web apps/web
RUN pnpm --filter @forgeai/web build

FROM node:22-slim AS runtime

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:////app/.forgeai/forgeai.db
ENV RUNNER_MODE=inline
ENV APPROVAL_MODE=required
ENV ENABLE_CLOUD_PLUGINS=false
ENV WEB_PROXY_URL=http://127.0.0.1:3000

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-venv git libgl1 libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*

COPY apps/api /app/apps/api
RUN python3 -m venv /opt/forgeai-venv \
  && /opt/forgeai-venv/bin/pip install --no-cache-dir --upgrade pip \
  && /opt/forgeai-venv/bin/pip install --no-cache-dir /app/apps/api

COPY --from=web-build /app/apps/web/.next/standalone ./
COPY --from=web-build /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=web-build /app/apps/web/public ./apps/web/public

RUN mkdir -p /app/.forgeai/artifacts

EXPOSE 8000

CMD ["sh", "-c", "HOSTNAME=127.0.0.1 PORT=3000 node apps/web/server.js & /opt/forgeai-venv/bin/uvicorn forgeai.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
