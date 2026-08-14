import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from forgeai.core.config import get_settings
from forgeai.core.logging import configure_logging
from forgeai.core.metrics import ACTIVE_RUNS, APPROVALS_RESOLVED, RUNS_CREATED, metrics_response
from forgeai.core.runner import execute_run
from forgeai.db.session import get_db, init_db
from forgeai.db.tables import ApprovalRequest, RunEvent, TaskRun
from forgeai.models import (
    ApprovalDecision,
    RepoIndexRequest,
    RunCreate,
    SearchResponseItem,
    TaskRunRead,
)
from forgeai.services.events import emit_event
from forgeai.services.indexer import index_repository, semantic_search
from forgeai.workers.tasks import execute_run_task

settings = get_settings()
configure_logging()
DbSession = Annotated[Session, Depends(get_db)]

app = FastAPI(
    title="ForgeAI API",
    version="0.1.0",
    description=(
        "Local-first software engineering control plane for approval-gated verified patches."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FastAPIInstrumentor.instrument_app(app)


@app.on_event("startup")
def startup() -> None:
    settings.ensure_runtime_dirs()
    init_db()


def _load_run(db: Session, run_id: str) -> TaskRun:
    run = db.execute(
        select(TaskRun)
        .options(
            selectinload(TaskRun.events),
            selectinload(TaskRun.steps),
            selectinload(TaskRun.approvals),
            selectinload(TaskRun.artifacts),
            selectinload(TaskRun.verified_patches),
            selectinload(TaskRun.llm_calls),
        )
        .where(TaskRun.id == run_id)
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def dispatch_run(run_id: str, background_tasks: BackgroundTasks, *, resume: bool = False) -> None:
    if settings.runner_mode == "celery":
        execute_run_task.delay(run_id, resume)
        return
    background_tasks.add_task(execute_run, run_id, resume=resume)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@app.get("/metrics")
def metrics():
    return metrics_response()


@app.post("/api/runs", response_model=TaskRunRead)
def create_run(
    payload: RunCreate,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> TaskRun:
    repo_path = payload.repo_path
    if repo_path:
        resolved = Path(repo_path).expanduser().resolve()
        if not resolved.exists():
            raise HTTPException(status_code=400, detail=f"repo_path does not exist: {resolved}")
        repo_path = str(resolved)
    run = TaskRun(
        task=payload.task,
        repo_path=repo_path,
        status="queued",
        model_profile=payload.model_profile,
        metadata_json=payload.metadata,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    RUNS_CREATED.inc()
    ACTIVE_RUNS.inc()
    emit_event(db, run.id, "Run queued.", agent="api", event_type="run_status")
    dispatch_run(run.id, background_tasks)
    return _load_run(db, run.id)


@app.get("/api/runs/{run_id}", response_model=TaskRunRead)
def get_run(run_id: str, db: DbSession) -> TaskRun:
    return _load_run(db, run_id)


@app.get("/api/runs/{run_id}/events")
async def stream_run_events(run_id: str, db: DbSession):
    if db.get(TaskRun, run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        last_sequence = 0
        idle_ticks = 0
        while idle_ticks < 900:
            stream_db = next(get_db())
            try:
                events = (
                    stream_db.execute(
                        select(RunEvent)
                        .where(RunEvent.run_id == run_id, RunEvent.sequence > last_sequence)
                        .order_by(RunEvent.sequence)
                    )
                    .scalars()
                    .all()
                )
                run = stream_db.get(TaskRun, run_id)
            finally:
                stream_db.close()
            for event in events:
                last_sequence = event.sequence
                idle_ticks = 0
                yield "event: run_event\n"
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "id": event.id,
                            "sequence": event.sequence,
                            "level": event.level,
                            "agent": event.agent,
                            "event_type": event.event_type,
                            "message": event.message,
                            "payload": event.payload,
                            "created_at": event.created_at.isoformat(),
                        }
                    )
                    + "\n\n"
                )
            if run and run.status in {"completed", "failed", "rejected"} and not events:
                yield "event: run_done\n"
                yield f"data: {json.dumps({'status': run.status})}\n\n"
                break
            idle_ticks += 1
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/runs/{run_id}/approvals/{approval_id}", response_model=TaskRunRead)
def resolve_approval(
    run_id: str,
    approval_id: str,
    decision: ApprovalDecision,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> TaskRun:
    run = db.get(TaskRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    approval = db.get(ApprovalRequest, approval_id)
    if approval is None or approval.run_id != run_id:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail="Approval has already been resolved")

    approval.status = decision.decision
    approval.resolved_at = datetime.utcnow()
    approval.resolved_by = decision.actor
    approval.payload = {**approval.payload, "reason": decision.reason}
    run.status = "running" if decision.decision == "approved" else "rejected"
    db.add_all([approval, run])
    db.commit()
    APPROVALS_RESOLVED.labels(decision=decision.decision).inc()
    emit_event(
        db,
        run_id,
        f"Approval {decision.decision} by {decision.actor}.",
        agent="approval-gate",
        event_type="approval_resolved",
        payload={"approval_id": approval.id, "decision": decision.decision},
    )
    if decision.decision == "approved":
        dispatch_run(run_id, background_tasks, resume=True)
    else:
        ACTIVE_RUNS.dec()
    return _load_run(db, run_id)


@app.post("/api/repos/index")
def index_repo(payload: RepoIndexRequest, db: DbSession) -> dict[str, object]:
    try:
        count = index_repository(db, payload.path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"indexed_chunks": count, "path": str(Path(payload.path).expanduser().resolve())}


@app.get("/api/search", response_model=list[SearchResponseItem])
def search(q: str = Query(min_length=1), limit: int = Query(default=8, ge=1, le=20)):
    return [
        SearchResponseItem(
            file_path=hit.file_path,
            content=hit.content,
            score=hit.score,
            language=hit.language,
        )
        for hit in semantic_search(q, limit=limit)
    ]


if settings.web_static_dir.exists():
    app.mount("/", StaticFiles(directory=settings.web_static_dir, html=True), name="web")
else:

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def proxy_dashboard(full_path: str, request: Request) -> Response:
        if not settings.web_proxy_url:
            raise HTTPException(status_code=404, detail="Dashboard is not mounted")

        base_url = settings.web_proxy_url.rstrip("/")
        target = f"{base_url}/{full_path}"
        if request.url.query:
            target = f"{target}?{request.url.query}"

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                target,
                headers={
                    "accept": request.headers.get("accept", "*/*"),
                    "user-agent": request.headers.get("user-agent", "forgeai-proxy"),
                },
            )
        headers = {
            key: value
            for key, value in upstream.headers.items()
            if key.lower() in {"content-type", "cache-control", "location"}
        }
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=headers,
        )
