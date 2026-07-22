from celery import Celery

from forgeai.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "forgeai",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["forgeai.workers.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
)
