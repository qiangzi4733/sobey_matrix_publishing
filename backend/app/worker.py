from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery("matrix", broker=settings.redis_url, backend=settings.redis_url, include=["app.tasks"])
celery_app.conf.update(
    timezone="Asia/Shanghai",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    beat_schedule={
        "dispatch-due-tasks": {"task": "app.tasks.dispatch_due_tasks", "schedule": 60.0},
        # 每 6 小时检测一次扫码登录的账号，失效及时提醒客户重新扫码
        "check-all-accounts": {"task": "app.tasks.check_all_accounts", "schedule": crontab(minute=0, hour="*/6")},
    },
)
if settings.wechat_mp_mock:
    celery_app.conf.beat_schedule["mock-push-component-ticket"] = {
        "task": "app.tasks.mock_push_component_ticket",
        "schedule": crontab(minute="*/10"),
    }


@celery_app.task
def ping() -> str:
    return "pong"
