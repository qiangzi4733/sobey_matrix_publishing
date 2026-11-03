import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app import tasks, verification
from app.config import get_settings
from app.deps import CurrentUser, DbSession
from app.models import Account, AccountStatus, Article, Platform, Post, PublishStatus, PublishTask, ReviewStatus
from app.platforms.scheduling import NATIVE_SCHEDULE, validate_native_schedule
from app.platforms.wechat_mp import ARTICLE_IMAGE_URL, article_image_path
from app.routers.categories import get_category, subtree_ids
from app.schemas import (
    ArticleIn,
    CodeIn,
    ImageOut,
    MoveCategoryIn,
    PostAccountOut,
    PostDetailOut,
    PostOut,
    PublishIn,
    PublishTaskOut,
    RejectIn,
    VerificationOut,
)
from app.security import create_video_token, verify_video_token

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


def _publish_account(db: DbSession, user: CurrentUser, account_id: int | None, allowed: set[Platform], kind: str) -> Account:
    account = db.get(Account, account_id) if account_id is not None else None
    if account is None or account.tenant_id != user.tenant_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "发布账号不存在或已被移除，请重新选择")
    if account.platform not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"「{account.display_name}」所在平台暂不支持发布{kind}")
    if account.status != AccountStatus.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"「{account.display_name}」登录已失效，请先重新登录")
    return account


def _post_category(db: DbSession, user: CurrentUser, category_id: int | None) -> int | None:
    if category_id is not None and get_category(db, user, category_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "分类不存在或已被删除，请重新选择")
    return category_id


def _check_schedule(scheduled_at: datetime | None, account: Account) -> None:
    if scheduled_at is None:
        return
    if scheduled_at.tzinfo is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "定时时间需要带时区")
    if scheduled_at <= datetime.now(UTC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "定时时间已经过去了")
    if account.platform in NATIVE_SCHEDULE:
        try:
            validate_native_schedule(account.platform, scheduled_at)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None


def _create_task(db: DbSession, user: CurrentUser, post: Post, account: Account) -> PublishTaskOut:
    # 平台自带定时的现在就提交给平台；其余由 beat 到点再入队
    native = account.platform in NATIVE_SCHEDULE
    task = PublishTask(
        tenant_id=user.tenant_id,
        account_id=account.id,
        account_name=account.display_name,
        platform=account.platform,
        status=PublishStatus.scheduled if post.scheduled_at and not native else PublishStatus.queued,
    )
    post.tasks = [task]
    db.add(post)
    db.commit()

    if task.status == PublishStatus.queued:
        tasks.enqueue_publish(task)
    return _task_out(task)


def _post_out(post: Post, detail: bool = False) -> PostOut:
    fields = dict(
        id=post.id,
        kind="article" if post.article else "video",
        title=post.title,
        review_status=post.review_status,
        review_note=post.review_note,
        reviewer_name=post.reviewer.name if post.reviewer else None,
        reviewed_at=post.reviewed_at,
        creator_name=post.creator.name if post.creator else None,
        account=PostAccountOut.model_validate(post.account) if post.account else None,
        category_id=post.category_id,
        scheduled_at=post.scheduled_at,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )
    if not detail:
        return PostOut(**fields)
    out = PostDetailOut(**fields, description=post.description, tags=post.tags)
    if post.article:
        out.author = post.article.author
        out.content = post.article.content
        out.cover_url = f"/api/{post.article.cover_path}"
        out.source_url = post.article.source_url
        out.open_comment = post.article.open_comment
        out.draft_only = post.article.draft_only
    else:
        out.video_url = f"/api/posts/{post.id}/video?token={create_video_token(post.id)}"
    return out


def _get_post(db: DbSession, user: CurrentUser, post_id: int, lock: bool = False) -> Post:
    # 修改、删除时锁住这一行，避免和同时进行的发布交错
    post = db.get(Post, post_id, with_for_update=lock)
    if post is None or post.tenant_id != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "内容不存在")
    return post


def _get_editable(db: DbSession, user: CurrentUser, post_id: int, kind: str) -> Post:
    post = _get_post(db, user, post_id, lock=True)
    if (post.article is not None) != (kind == "article"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "内容不存在")
    if post.review_status == ReviewStatus.published:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "已发布的内容不能修改")
    return post


def _submit_for_review(db: DbSession, post: Post, account: Account) -> PostOut:
    """新建或修改后都回到待审核，上一轮的审核结果清空。"""
    post.account = account
    post.review_status = ReviewStatus.pending
    post.review_note = None
    post.reviewed_by = None
    post.reviewed_at = None
    db.add(post)
    db.commit()
    return _post_out(post)


def _save_video(user: CurrentUser, video: UploadFile) -> str:
    suffix = Path(video.filename or "").suffix.lower()
    if suffix not in VIDEO_SUFFIXES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "只支持 mp4 / mov 视频")
    relative = Path(str(user.tenant_id)) / f"{uuid.uuid4().hex}{suffix}"
    target = Path(get_settings().media_dir) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as out:
        shutil.copyfileobj(video.file, out, length=1024 * 1024)
    return str(relative)


def _copy_video(db: DbSession, user: CurrentUser, source_id: int) -> str:
    source = _get_post(db, user, source_id)
    media_dir = Path(get_settings().media_dir)
    if source.article is not None or not (media_dir / source.video_path).is_file():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "要复制的视频不存在")
    relative = Path(str(user.tenant_id)) / f"{uuid.uuid4().hex}{Path(source.video_path).suffix}"
    # 删除内容时会删掉它的视频文件，所以不能和原内容共用路径；硬链接不占额外空间，不支持时才真的复制
    try:
        os.link(media_dir / source.video_path, media_dir / relative)
    except OSError:
        shutil.copyfile(media_dir / source.video_path, media_dir / relative)
    return str(relative)


def _remove_video(post: Post) -> None:
    if post.video_path:
        (Path(get_settings().media_dir) / post.video_path).unlink(missing_ok=True)


@router.post("/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    db: DbSession,
    user: CurrentUser,
    title: Annotated[str, Form(min_length=1, max_length=200)],
    account_id: Annotated[int, Form()],
    category_id: Annotated[int | None, Form(description="不传为未分类")] = None,
    description: Annotated[str, Form(max_length=1000)] = "",
    tags: Annotated[str, Form(description="逗号分隔的话题，不带 #")] = "",
    scheduled_at: Annotated[datetime | None, Form()] = None,
    video: Annotated[UploadFile | None, File()] = None,
    copy_from: Annotated[int | None, Form(description="复制这条内容的视频，不用重新上传")] = None,
) -> PostOut:
    """上传视频并提交审核；审核通过后手动发布到选中的账号。"""
    if (video is None) == (copy_from is None):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择视频")
    account = _publish_account(db, user, account_id, tasks.VIDEO_PLATFORMS, "视频")
    _check_schedule(scheduled_at, account)
    post = Post(
        tenant_id=user.tenant_id,
        created_by=user.id,
        title=title,
        description=description,
        tags=[t.lstrip("#") for t in _split(tags)],
        video_path=_save_video(user, video) if video is not None else _copy_video(db, user, copy_from),
        scheduled_at=scheduled_at,
        category_id=_post_category(db, user, category_id),
    )
    return _submit_for_review(db, post, account)


@router.put("/posts/{post_id}", response_model=PostOut)
def update_post(
    post_id: int,
    db: DbSession,
    user: CurrentUser,
    title: Annotated[str, Form(min_length=1, max_length=200)],
    account_id: Annotated[int, Form()],
    category_id: Annotated[int | None, Form(description="不传为未分类")] = None,
    description: Annotated[str, Form(max_length=1000)] = "",
    tags: Annotated[str, Form(description="逗号分隔的话题，不带 #")] = "",
    scheduled_at: Annotated[datetime | None, Form()] = None,
    video: Annotated[UploadFile | None, File(description="不传则沿用原视频")] = None,
) -> PostOut:
    post = _get_editable(db, user, post_id, "video")
    account = _publish_account(db, user, account_id, tasks.VIDEO_PLATFORMS, "视频")
    _check_schedule(scheduled_at, account)
    if video is not None:
        _remove_video(post)
        post.video_path = _save_video(user, video)
    post.title = title
    post.description = description
    post.tags = [t.lstrip("#") for t in _split(tags)]
    post.scheduled_at = scheduled_at
    post.category_id = _post_category(db, user, category_id)
    return _submit_for_review(db, post, account)


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


def _article_cover(body: ArticleIn, user: CurrentUser) -> str:
    # 只能引用本租户上传的图片
    cover = ARTICLE_IMAGE_URL.fullmatch(f'src="{body.cover_url}"')
    if not cover or cover.group(1) != str(user.tenant_id) or not article_image_path(*cover.groups()).is_file():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请上传封面")
    if any(m.group(1) != str(user.tenant_id) for m in ARTICLE_IMAGE_URL.finditer(body.content)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "正文里有无法使用的图片")
    return str(Path("article-images") / cover.group(1) / cover.group(2))


def _fill_article(post: Post, body: ArticleIn, cover_path: str) -> None:
    post.title = body.title
    post.description = body.digest
    post.scheduled_at = body.scheduled_at
    if post.article is None:
        post.article = Article()
    post.article.author = body.author
    post.article.content = body.content
    post.article.cover_path = cover_path
    post.article.source_url = body.source_url
    post.article.open_comment = body.open_comment
    post.article.draft_only = body.draft_only


@router.post("/articles", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_article(body: ArticleIn, db: DbSession, user: CurrentUser) -> PostOut:
    """提交图文审核；审核通过后手动发布到选中的公众号，draft_only 时只存草稿箱。"""
    account = _publish_account(db, user, body.account_id, tasks.ARTICLE_PLATFORMS, "图文")
    _check_schedule(body.scheduled_at, account)
    cover_path = _article_cover(body, user)
    post = Post(
        tenant_id=user.tenant_id,
        created_by=user.id,
        tags=[],
        video_path="",
        category_id=_post_category(db, user, body.category_id),
    )
    _fill_article(post, body, cover_path)
    return _submit_for_review(db, post, account)


@router.put("/articles/{post_id}", response_model=PostOut)
def update_article(post_id: int, body: ArticleIn, db: DbSession, user: CurrentUser) -> PostOut:
    post = _get_editable(db, user, post_id, "article")
    account = _publish_account(db, user, body.account_id, tasks.ARTICLE_PLATFORMS, "图文")
    _check_schedule(body.scheduled_at, account)
    _fill_article(post, body, _article_cover(body, user))
    post.category_id = _post_category(db, user, body.category_id)
    return _submit_for_review(db, post, account)


@router.get("/posts", response_model=list[PostOut])
def list_posts(
    db: DbSession,
    user: CurrentUser,
    review_status: ReviewStatus | None = None,
    category_id: int | None = None,
    uncategorized: bool = False,
    mine: bool = False,
    limit: int = 100,
) -> list[PostOut]:
    """category_id 包含下级分类；uncategorized 只看未分类；mine 只看自己提交的。"""
    query = select(Post).where(Post.tenant_id == user.tenant_id)
    if review_status:
        query = query.where(Post.review_status == review_status)
    if category_id is not None:
        query = query.where(Post.category_id.in_(subtree_ids(db, user, category_id)))
    elif uncategorized:
        query = query.where(Post.category_id.is_(None))
    if mine:
        query = query.where(Post.created_by == user.id)
    rows = db.scalars(
        query.options(
            selectinload(Post.article), selectinload(Post.account), selectinload(Post.creator), selectinload(Post.reviewer)
        )
        .order_by(Post.id.desc())
        .limit(min(limit, 500))
    ).all()
    return [_post_out(post) for post in rows]


@router.post("/posts/category", response_model=int)
def move_category(body: MoveCategoryIn, db: DbSession, user: CurrentUser) -> int:
    """批量移到某个分类，返回移动的条数。分类只是归档，任何状态（包括已发布）都能移，也不需要重新审核。"""
    category_id = _post_category(db, user, body.category_id)
    moved = db.execute(
        update(Post)
        .where(Post.tenant_id == user.tenant_id, Post.id.in_(body.post_ids))
        # 列表里的「提交时间」用的是 updated_at，移动分类不算修改内容
        .values(category_id=category_id, updated_at=Post.updated_at)
    ).rowcount
    db.commit()
    return moved


@router.get("/posts/{post_id}", response_model=PostDetailOut)
def get_post(post_id: int, db: DbSession, user: CurrentUser) -> PostDetailOut:
    return _post_out(_get_post(db, user, post_id), detail=True)


# 不用登录令牌，用 create_video_token 签的预览令牌，见 app.security
@router.get("/posts/{post_id}/video")
def post_video(post_id: int, token: str, db: DbSession) -> FileResponse:
    post = db.get(Post, post_id)
    if post is None or not post.video_path or not verify_video_token(token, post_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "视频不存在")
    return FileResponse(Path(get_settings().media_dir) / post.video_path)


def _transition(db: DbSession, post: Post, before: ReviewStatus, error: str, **values) -> None:
    """按当前状态条件更新，重复点击或并发操作只有一次生效。"""
    changed = db.execute(
        update(Post).where(Post.id == post.id, Post.review_status == before).values(**values)
    ).rowcount
    if not changed:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, error)


@router.post("/posts/{post_id}/approve", response_model=PostOut)
def approve_post(post_id: int, db: DbSession, user: CurrentUser) -> PostOut:
    post = _get_post(db, user, post_id)
    _transition(
        db, post, ReviewStatus.pending, "只有待审核的内容可以审核",
        review_status=ReviewStatus.approved, review_note=None, reviewed_by=user.id, reviewed_at=datetime.now(UTC),
    )
    db.commit()
    db.refresh(post)
    return _post_out(post)


@router.post("/posts/{post_id}/reject", response_model=PostOut)
def reject_post(post_id: int, body: RejectIn, db: DbSession, user: CurrentUser) -> PostOut:
    post = _get_post(db, user, post_id)
    _transition(
        db, post, ReviewStatus.pending, "只有待审核的内容可以退回",
        review_status=ReviewStatus.rejected, review_note=body.note, reviewed_by=user.id, reviewed_at=datetime.now(UTC),
    )
    db.commit()
    db.refresh(post)
    return _post_out(post)


@router.post("/posts/{post_id}/publish", response_model=PublishTaskOut)
def publish_post(post_id: int, body: PublishIn, db: DbSession, user: CurrentUser) -> PublishTaskOut:
    """审核通过的内容生成发布任务。账号和定时在这里重新校验：审核期间可能已失效或过期。"""
    post = _get_post(db, user, post_id)
    if post.review_status != ReviewStatus.approved:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "只有审核通过的内容可以发布")
    if post.article:
        account = _publish_account(db, user, post.account_id, tasks.ARTICLE_PLATFORMS, "图文")
    else:
        account = _publish_account(db, user, post.account_id, tasks.VIDEO_PLATFORMS, "视频")
    _check_schedule(body.scheduled_at, account)
    _transition(
        db, post, ReviewStatus.approved, "这条内容已经发布过了",
        review_status=ReviewStatus.published, scheduled_at=body.scheduled_at,
    )
    db.refresh(post)
    return _create_task(db, user, post, account)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int, db: DbSession, user: CurrentUser) -> None:
    post = _get_post(db, user, post_id, lock=True)
    if post.review_status == ReviewStatus.published:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "已发布的内容不能删除")
    db.delete(post)
    db.commit()
    _remove_video(post)


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
