from celery import Celery

from app.config import settings


celery_app = Celery(
    "code_executor",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.execution_timeout + 30,
    task_soft_time_limit=settings.execution_timeout + 10,
    worker_prefetch_multiplier=1,
    worker_concurrency=settings.celery_worker_concurrency,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

celery_app.conf.beat_schedule = {
    "cleanup-expired-sessions": {
        "task": "app.worker.tasks.cleanup_expired_sessions",
        "schedule": 300.0,  # every 5 minutes
    },
}

