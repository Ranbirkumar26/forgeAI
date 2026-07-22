from forgeai.core.runner import execute_run
from forgeai.workers.celery_app import celery_app


@celery_app.task(name="forgeai.execute_run")
def execute_run_task(run_id: str, resume: bool = False) -> None:
    execute_run(run_id, resume=resume)
