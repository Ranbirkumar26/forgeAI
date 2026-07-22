import logging

from sqlalchemy import select

from forgeai.core.graph import build_forge_graph
from forgeai.db.session import SessionLocal
from forgeai.db.tables import ApprovalRequest, TaskRun
from forgeai.services.events import emit_event, set_run_status

logger = logging.getLogger(__name__)


def execute_run(run_id: str, *, resume: bool = False) -> None:
    with SessionLocal() as db:
        run = db.get(TaskRun, run_id)
        if run is None:
            logger.error("Run not found: %s", run_id)
            return
        run.status = "running"
        db.add(run)
        db.commit()
        emit_event(
            db,
            run_id,
            "Run resumed." if resume else "Run started.",
            agent="orchestrator",
            event_type="run_status",
        )
        state = {
            "run_id": run.id,
            "task": run.task,
            "repo_path": run.repo_path,
            "model_profile": run.model_profile,
            "halted": False,
        }

    try:
        graph = build_forge_graph()
        final_state = graph.invoke(state)
        with SessionLocal() as db:
            pending = db.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.run_id == run_id,
                    ApprovalRequest.status == "pending",
                )
            ).scalar_one_or_none()
            if pending or final_state.get("halted"):
                set_run_status(db, run_id, "awaiting_approval")
                return
            emit_event(db, run_id, "Run completed.", agent="orchestrator", event_type="run_status")
            set_run_status(db, run_id, "completed")
    except Exception as exc:  # pragma: no cover - exercised by integration failures
        logger.exception("Run failed: %s", run_id)
        with SessionLocal() as db:
            emit_event(
                db,
                run_id,
                f"Run failed: {exc}",
                agent="orchestrator",
                level="error",
                event_type="run_failed",
            )
            set_run_status(db, run_id, "failed")
