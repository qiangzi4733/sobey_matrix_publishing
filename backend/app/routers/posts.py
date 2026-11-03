import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import tasks, verification
from app.config import get_settings
from app.deps import CurrentUser, DbSession
from app.models import Account, AccountStatus, Article, Platform, Post, PublishStatus, PublishTask
from app.platforms.scheduling import NATIVE_SCHEDULE, validate_native_schedule
from app.platforms.wechat_mp import ARTICLE_IMAGE_URL, article_image_path
from app.schemas import ArticleIn, CodeIn, ImageOut, PublishTaskOut, VerificationOut

router = APIRouter(prefix="/api", tags=["publish"])

VIDEO_SUFFIXES = {".mp4", ".mov"}
# 公众号正文图片只支持 jpg/png、1MB 以内；封面（永久素材）10MB 以内，这里统一按正文图片的要求
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
IMAGE_MAX_BYTES = 1024 * 1024


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]


def _task_out(task: PublishTask) -> PublishTaskOut:
    return PublishTaskOut(
        id=task.id,
        post_id=task.post_id,
        title=task.post.title,
        account_id=task.account_id,
        account_name=task.account_name,
        platform=task.platform,
        status=task.status,
        error=task.error,
        has_screenshot=bool(task.screenshot_path),
        url=task.result.url if task.result else None,
        draft=bool(task.result and task.result.data.get("draft")),
        needs_code=task.status == PublishStatus.running and verification.pending(f"task:{task.id}") is not None,
        scheduled_at=task.post.scheduled_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_at=task.created_at,
    )


def _publish_accounts(db: DbSession, user: CurrentUser, ids: set[int], allowed: set[Platform], kind: str) -> list[Account]:
    accounts = db.scalars(select(Account).where(Account.id.in_(ids), Account.tenant_id == user.tenant_id)).all()
    if not ids or len(accounts) != len(ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择要发布的账号")
    for account in accounts:
        if account.platform not in allowed:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"「{account.display_name}」所在平台暂不支持发布{kind}")
        if account.status != AccountStatus.active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"「{account.display_name}」登录已失效，请先重新登录")
    return list(accounts)


def _check_schedule(scheduled_at: datetime | None, accounts: list[Account]) -> None:
    if scheduled_at is None:
        return
    if scheduled_at.tzinfo is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "定时时间需要带时区")
    if scheduled_at <= datetime.now(UTC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "定时时间已经过去了")
    for platform in {a.platform for a in accounts} & NATIVE_SCHEDULE.keys():
        try:
            validate_native_schedule(platform, scheduled_at)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None


def _submit(db: DbSession, user: CurrentUser, post: Post, accounts: list[Account]) -> list[PublishTaskOut]:
    def initial_status(account: Account) -> PublishStatus:
        # 平台自带定时的现在就提交给平台；其余由 beat 到点再入队
        if post.scheduled_at and account.platform not in NATIVE_SCHEDULE:
            return PublishStatus.scheduled
        return PublishStatus.queued

    post.tasks = [
        PublishTask(
            tenant_id=user.tenant_id,
            account_id=account.id,
            account_name=account.display_name,
            platform=account.platform,
            status=initial_status(account),
        )
        for account in accounts
    ]
    db.add(post)
    db.commit()

    for task in post.tasks:
        if task.status == PublishStatus.queued:
            tasks.enqueue_publish(task)
    return [_task_out(task) for task in post.tasks]


@router.post("/posts", response_model=list[PublishTaskOut], status_code=status.HTTP_201_CREATED)
def create_post(
    db: DbSession,
    user: CurrentUser,
    video: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=1, max_length=200)],
    account_ids: Annotated[str, Form(description="逗号分隔的账号 ID")],
    description: Annotated[str, Form(max_length=1000)] = "",
    tags: Annotated[str, Form(description="逗号分隔的话题，不带 #")] = "",
    scheduled_at: Annotated[datetime | None, Form()] = None,
) -> list[PublishTaskOut]:
    """上传视频并发布到选中的多个账号，每个账号生成一条发布任务。"""
    suffix = Path(video.filename or "").suffix.lower()
    if suffix not in VIDEO_SUFFIXES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "只支持 mp4 / mov 视频")

    try:
        ids = {int(i) for i in _split(account_ids)}
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "账号参数不正确") from None
    accounts = _publish_accounts(db, user, ids, tasks.VIDEO_PLATFORMS, "视频")
    _check_schedule(scheduled_at, accounts)

    relative = Path(str(user.tenant_id)) / f"{uuid.uuid4().hex}{suffix}"
    target = Path(get_settings().media_dir) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as out:
        shutil.copyfileobj(video.file, out, length=1024 * 1024)

    post = Post(
        tenant_id=user.tenant_id,
        created_by=user.id,
        title=title,
        description=description,
        tags=[t.lstrip("#") for t in _split(tags)],
        video_path=str(relative),
        scheduled_at=scheduled_at,
    )
    return _submit(db, user, post, accounts)


@router.post("/article-images", response_model=ImageOut, status_code=status.HTTP_201_CREATED)
def upload_article_image(user: CurrentUser, image: Annotated[UploadFile, File()]) -> ImageOut:
    """上传图文的正文图片或封面，返回在编辑器里引用的地址。"""
    suffix = Path(image.filename or "").suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "只支持 jpg / png 图片")
    data = image.file.read(IMAGE_MAX_BYTES + 1)
    if len(data) > IMAGE_MAX_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "图片不能超过 1MB")
    name = f"{uuid.uuid4().hex}{suffix}"
    target = article_image_path(user.tenant_id, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return ImageOut(url=f"/api/article-images/{user.tenant_id}/{name}")


# 不校验登录：编辑器里的 <img> 带不上令牌。文件名是随机 UUID，无法枚举
@router.get("/article-images/{tenant_id}/{name}")
def article_image(tenant_id: int, name: str) -> FileResponse:
    path = article_image_path(tenant_id, name)
    if not ARTICLE_IMAGE_URL.fullmatch(f'src="/api/article-images/{tenant_id}/{name}"') or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "图片不存在")
    return FileResponse(path)


@router.post("/articles", response_model=list[PublishTaskOut], status_code=status.HTTP_201_CREATED)
def create_article(body: ArticleIn, db: DbSession, user: CurrentUser) -> list[PublishTaskOut]:
    """发布图文到选中的公众号；draft_only 时只存草稿箱。"""
    accounts = _publish_accounts(db, user, set(body.account_ids), tasks.ARTICLE_PLATFORMS, "图文")
    _check_schedule(body.scheduled_at, accounts)

    # 只能引用本租户上传的图片
    cover = ARTICLE_IMAGE_URL.fullmatch(f'src="{body.cover_url}"')
    if not cover or cover.group(1) != str(user.tenant_id) or not article_image_path(*cover.groups()).is_file():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请上传封面")
    if any(m.group(1) != str(user.tenant_id) for m in ARTICLE_IMAGE_URL.finditer(body.content)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "正文里有无法使用的图片")

    post = Post(
        tenant_id=user.tenant_id,
        created_by=user.id,
        title=body.title,
        description=body.digest,
        tags=[],
        video_path="",
        scheduled_at=body.scheduled_at,
    )
    post.article = Article(
        author=body.author,
        content=body.content,
        cover_path=str(Path("article-images") / cover.group(1) / cover.group(2)),
        source_url=body.source_url,
        open_comment=body.open_comment,
        draft_only=body.draft_only,
    )
    return _submit(db, user, post, accounts)


@router.get("/publish-tasks", response_model=list[PublishTaskOut])
def list_tasks(db: DbSession, user: CurrentUser, limit: int = 100) -> list[PublishTaskOut]:
    rows = db.scalars(
        select(PublishTask)
        .where(PublishTask.tenant_id == user.tenant_id)
        .options(selectinload(PublishTask.post), selectinload(PublishTask.result))
        .order_by(PublishTask.id.desc())
        .limit(min(limit, 500))
    ).all()
    return [_task_out(task) for task in rows]


def _get_task(db: DbSession, user: CurrentUser, task_id: int) -> PublishTask:
    task = db.get(PublishTask, task_id)
    if task is None or task.tenant_id != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    return task


@router.post("/publish-tasks/{task_id}/retry", response_model=PublishTaskOut)
def retry_task(task_id: int, db: DbSession, user: CurrentUser) -> PublishTaskOut:
    task = _get_task(db, user, task_id)
    if task.status != PublishStatus.failed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "只有失败的任务可以重试")
    task.status = PublishStatus.queued
    task.error = None
    task.finished_at = None
    db.commit()
    tasks.enqueue_publish(task)
    return _task_out(task)


@router.get("/publish-tasks/{task_id}/screenshot")
def task_screenshot(task_id: int, db: DbSession, user: CurrentUser) -> FileResponse:
    task = _get_task(db, user, task_id)
    if not task.screenshot_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "没有截图")
    return FileResponse(Path(get_settings().debug_dir) / Path(task.screenshot_path).name, media_type="image/png")


@router.get("/publish-tasks/{task_id}/verification", response_model=VerificationOut)
def task_verification(task_id: int, db: DbSession, user: CurrentUser) -> VerificationOut:
    _get_task(db, user, task_id)
    pending = verification.pending(f"task:{task_id}")
    if pending is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "当前不需要验证码")
    return VerificationOut(**pending)


@router.post("/publish-tasks/{task_id}/code", status_code=status.HTTP_204_NO_CONTENT)
def submit_task_code(task_id: int, body: CodeIn, db: DbSession, user: CurrentUser) -> None:
    _get_task(db, user, task_id)
    if not verification.submit(f"task:{task_id}", body.code):
        raise HTTPException(status.HTTP_409_CONFLICT, "当前不需要验证码")
