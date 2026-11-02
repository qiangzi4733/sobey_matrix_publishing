from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery("matrix", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(timezone="Asia/Shanghai", task_acks_late=True, worker_prefetch_multiplier=1)


@celery_app.task
def ping() -> str:
    return "pong"
