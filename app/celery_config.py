import os
import sys
from core.config import settings
from celery import Celery

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

REDIS_URL = "redis://default:password@localhost:6377/0"

BROKER_URL = settings.REDIS_URL

celery_app = Celery(
    "worker",
    backend=f"{BROKER_URL}",
    broker=f"{BROKER_URL}"
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_retry_on_failure=True,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    task_default_queue="default",
    task_routes={
        "tasks.ride.tasks.send_ride_notifications": {"queue": "notifications"},
    }
)

# celery_app.conf.broker_url = "redis://default:password@localhost:6377"

celery_app.autodiscover_tasks(
    [
        "tasks.notifications",
        "tasks.notifications.send_email",
    ]
)
