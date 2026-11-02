"""后台任务。浏览器类任务（登录、检测、发布）路由到 browser 队列，由 browser-worker 执行；
平台模块在任务内部导入，这样 backend / 普通 worker 不需要安装浏览器依赖。"""

import base64
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, update

from app import login_sessions, verification
from app.config import get_settings
from app.db import SessionLocal
from app.models import Account, AccountStatus, Platform, Post, PublishStatus, PublishTask
from app.platforms.base import LoginExpired, PublishError
from app.security import decrypt_credentials, encrypt_credentials
from app.worker import celery_app

log = logging.getLogger(__name__)

BROWSER_QUEUE = "browser"
# 扫码登录的平台；已支持发布的平台。公众号、快手接入后再加
BROWSER_PLATFORMS = {Platform.channels, Platform.douyin}
PUBLISHABLE = {Platform.channels, Platform.douyin}


def _now() -> datetime:
    return datetime.now(UTC)


def _browser_module(platform: Platform):
    """浏览器类平台的实现模块（login / check / publish 接口一致）。"""
    if platform == Platform.channels:
        from app.platforms import channels

        return channels
    if platform == Platform.douyin:
        from app.platforms import douyin

        return douyin
    raise PublishError("该平台暂不支持")


# ---------- 扫码登录 ----------


@celery_app.task(time_limit=900)
def qr_login(login_id: str) -> None:
    session = login_sessions.get(login_id)
    if session is None:
        return
    tenant_id = session["tenant_id"]
    platform = Platform(session["platform"])
    module = _browser_module(platform)

    def on_qr(png: bytes) -> None:
        login_sessions.update(
            login_id,
            status="waiting",
            message="请用账号管理员的手机扫码",
            qr="data:image/png;base64," + base64.b64encode(png).decode(),
        )

    def on_status(status: str, message: str) -> None:
        login_sessions.update(login_id, status=status, message=message)

    ask_code = verification.asker(f"login:{login_id}")
    try:
        state, profile = module.login(on_qr, on_status, ask_code)
    except TimeoutError:
        login_sessions.update(login_id, status="failed", message="二维码已超时，请重新获取", qr=None)
        return
    except Exception as exc:
        log.exception("扫码登录失败")
        login_sessions.update(login_id, status="failed", message=f"登录失败：{exc}", qr=None)
        return

    with SessionLocal() as db:
        account = db.scalar(
            select(Account).where(
                Account.tenant_id == tenant_id,
                Account.platform == platform,
                Account.external_id == profile["external_id"],
            )
        )
        if account is None:
            account = Account(
                tenant_id=tenant_id,
                platform=platform,
                external_id=profile["external_id"],
                display_name=profile.get("nickname") or profile["external_id"],
            )
            db.add(account)
        account.avatar_url = profile.get("avatar_url") or account.avatar_url
        account.credentials_encrypted = encrypt_credentials({"storage_state": state})
        account.status = AccountStatus.active
        account.last_checked_at = _now()
        db.commit()
        login_sessions.update(
            login_id, status="success", message=f"已添加「{account.display_name}」", qr=None, account_id=account.id
        )


# ---------- 登录状态检测 ----------


@celery_app.task(time_limit=180)
def check_account(account_id: int) -> str:
    with SessionLocal() as db:
        account = db.get(Account, account_id)
        if account is None or account.platform not in BROWSER_PLATFORMS or not account.credentials_encrypted:
            return "skipped"

        module = _browser_module(account.platform)
        state = decrypt_credentials(account.credentials_encrypted)["storage_state"]
        try:
            new_state = module.check(state)
        except LoginExpired:
            account.status = AccountStatus.expired
        except Exception:
            # 网络等临时问题不改账号状态，下次再检测
            log.exception("检测账号 %s 出错", account_id)
            return "error"
        else:
            account.credentials_encrypted = encrypt_credentials({"storage_state": new_state})
            account.status = AccountStatus.active
        account.last_checked_at = _now()
        db.commit()
        return account.status.value


@celery_app.task
def check_all_accounts() -> int:
    """定时任务：逐个检测浏览器类账号，顺便让平台续期 cookie。"""
    with SessionLocal() as db:
        ids = db.scalars(
            select(Account.id).where(
                Account.platform.in_(BROWSER_PLATFORMS), Account.status != AccountStatus.expired
            )
        ).all()
    for account_id in ids:
        check_account.apply_async(args=[account_id], queue=BROWSER_QUEUE)
    return len(ids)


# ---------- 发布 ----------


def enqueue_publish(task: PublishTask) -> None:
    queue = BROWSER_QUEUE if task.platform in BROWSER_PLATFORMS else "celery"
    run_publish_task.apply_async(args=[task.id], queue=queue)


@celery_app.task
def dispatch_due_tasks() -> int:
    """定时任务：把到点的定时发布放进队列。"""
    with SessionLocal() as db:
        due = db.scalars(
            select(PublishTask)
            .join(Post, PublishTask.post_id == Post.id)
            .where(PublishTask.status == PublishStatus.scheduled, Post.scheduled_at <= _now())
        ).all()
        for task in due:
            task.status = PublishStatus.queued
        db.commit()
        for task in due:
            enqueue_publish(task)
        return len(due)


# 发布不可重复执行：不用 acks_late，worker 中途崩溃宁可漏发也不重复发
@celery_app.task(acks_late=False, time_limit=2 * 3600)
def run_publish_task(task_id: int) -> None:
    with SessionLocal() as db:
        claimed = db.execute(
            update(PublishTask)
            .where(PublishTask.id == task_id, PublishTask.status == PublishStatus.queued)
            .values(status=PublishStatus.running, started_at=_now(), error=None, screenshot_path=None)
        ).rowcount
        db.commit()
        if not claimed:
            return

        task = db.get(PublishTask, task_id)
        account = task.account
        try:
            if account is None:
                raise PublishError("账号已被移除")
            if account.status != AccountStatus.active or not account.credentials_encrypted:
                raise PublishError("账号登录已失效，请重新扫码登录")
            if task.platform not in PUBLISHABLE:
                raise PublishError("该平台暂不支持发布")

            module = _browser_module(task.platform)
            post = task.post
            state = decrypt_credentials(account.credentials_encrypted)["storage_state"]
            new_state = module.publish(
                state,
                Path(get_settings().media_dir) / post.video_path,
                title=post.title,
                description=post.description,
                tags=post.tags,
                schedule_at=post.scheduled_at,
                ask_code=verification.asker(f"task:{task_id}"),
            )
            account.credentials_encrypted = encrypt_credentials({"storage_state": new_state})
            task.status = PublishStatus.success
        except LoginExpired as exc:
            account.status = AccountStatus.expired
            task.status = PublishStatus.failed
            task.error = f"{exc}，请重新扫码登录"
        except PublishError as exc:
            task.status = PublishStatus.failed
            task.error = str(exc)
            task.screenshot_path = exc.screenshot
        except Exception as exc:
            log.exception("发布任务 %s 失败", task_id)
            task.status = PublishStatus.failed
            task.error = f"发布失败：{exc}"
        task.finished_at = _now()
        db.commit()
