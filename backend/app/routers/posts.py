import json
import os
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, get_args

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import selectinload

from app import tasks, verification
from app.config import get_settings
from app.deps import CurrentUser, DbSession
from app.models import Account, AccountStatus, Article, Category, Platform, Post, PublishStatus, PublishTask, ReviewStatus
from app.platforms import video_options
from app.platforms.scheduling import NATIVE_SCHEDULE, validate_native_schedule
from app.platforms.wechat_mp import ARTICLE_IMAGE_URL, article_image_path
from app.routers.categories import get_category, subtree_ids
from app.schemas import (
    ArticleIn,
    CodeIn,
    ImageOut,
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
# 视频封面（通用的竖封面和平台专属配置里的图片）。各平台上限不一，按较宽的 5MB，平台自己会再压缩
VIDEO_COVER_MAX_BYTES = 5 * 1024 * 1024
VIDEO_COVER_URL = re.compile(r"/api/(video-covers/(\d+)/[0-9a-f]{32}\.(?:jpg|jpeg|png))")


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
        # 内容在失败后被修改过，这条旧任务不能再重试（新内容要重新审核）
        can_retry=task.status == PublishStatus.failed and task.post.current_task_id == task.id,
        scheduled_at=task.post.scheduled_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_at=task.created_at,
    )


def _publish_account(
    db: DbSession, user: CurrentUser, account_id: int | None, allowed: set[Platform], kind: str, draft: bool = False
) -> Account | None:
    """草稿可以先不选账号，选了的账号失效也没关系，提交审核时再校验。"""
    if draft and account_id is None:
        return None
    account = db.get(Account, account_id) if account_id is not None else None
    if account is None or account.tenant_id != user.tenant_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "发布账号不存在或已被移除，请重新选择")
    if account.platform not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"「{account.display_name}」所在平台暂不支持发布{kind}")
    if account.status != AccountStatus.active and not draft:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"「{account.display_name}」登录已失效，请先重新登录")
    return account


def _new_post_category(db: DbSession, user: CurrentUser, category_id: int | None) -> Category:
    """新建（包括复制）只能放进绑定了账号的分类，发布账号由分类决定。"""
    category = get_category(db, user, category_id) if category_id is not None else None
    if category is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "分类不存在或已被删除，请重新选择")
    if category.account_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"「{category.name}」还没有绑定发布账号，请先在分类管理里绑定")
    return category


def _edit_account_id(post: Post, account_id: int | None) -> int | None:
    """修改时发到哪个账号（分类不能改）。分类绑定了账号时客户不能选：草稿跟着分类当前的绑定，
    已提交过的沿用原来的账号，原账号被移除了才改用分类的。分类没绑定的老内容由客户选。"""
    category = post.category
    if category is None or category.account_id is None:
        return account_id
    if post.review_status == ReviewStatus.draft or post.account_id is None:
        return category.account_id
    return post.account_id


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
        post=post,
    )
    post.current_task = task
    db.commit()

    if task.status == PublishStatus.queued:
        tasks.enqueue_publish(task)
    return _task_out(task)


def _publish_status(post: Post) -> str | None:
    """发布状态，按这一轮的发布任务算；没点过「发布」为空。"""
    task = post.current_task
    if task is None:
        return None
    if task.status in (PublishStatus.queued, PublishStatus.running):
        return "publishing"
    if task.status == PublishStatus.scheduled:
        return "scheduled"
    if task.status == PublishStatus.failed:
        return "failed"
    # 平台自带定时的，提交成功只是交给了平台，到点才对外可见
    if post.scheduled_at and post.scheduled_at > datetime.now(UTC):
        return "scheduled"
    if task.result and task.result.data.get("draft"):
        return "draft_saved"
    return "success"


def _cover_url(post: Post) -> str:
    path = post.article.cover_path if post.article else post.cover_path
    return f"/api/{path}" if path else ""


def _post_out(post: Post, detail: bool = False) -> PostOut:
    task = post.current_task
    fields = dict(
        id=post.id,
        kind="article" if post.article else "video",
        title=post.title,
        review_status=post.review_status,
        publish_status=_publish_status(post),
        # 账号被移除后，已发布的内容仍能看出发到了哪个账号
        account_name=task.account_name if task else None,
        review_note=post.review_note,
        reviewer_name=post.reviewer.name if post.reviewer else None,
        reviewed_at=post.reviewed_at,
        creator_name=post.creator.name if post.creator else None,
        account=PostAccountOut.model_validate(post.account) if post.account else None,
        category_id=post.category_id,
        scheduled_at=post.scheduled_at,
        created_at=post.created_at,
        updated_at=post.updated_at,
        cover_url=_cover_url(post),
    )
    if not detail:
        return PostOut(**fields)
    out = PostDetailOut(**fields, description=post.description, tags=post.tags)
    # 图片字段在库里是路径，给前端换回地址
    out.options = {
        key: f"/api/{value}" if key in video_options.IMAGE_FIELDS else value for key, value in post.options.items()
    }
    if post.article:
        out.author = post.article.author
        out.content = post.article.content
        out.source_url = post.article.source_url
        out.open_comment = post.article.open_comment
        out.draft_only = post.article.draft_only
    elif post.video_path:
        out.video_url = f"/api/posts/{post.id}/video?token={create_video_token(post.id)}"
    return out


def _get_post(db: DbSession, user: CurrentUser, post_id: int, lock: bool = False) -> Post:
    # 修改、删除时锁住这一行，避免和同时进行的发布交错
    post = db.get(Post, post_id, with_for_update=lock)
    if post is None or post.tenant_id != user.tenant_id or not _visible(post, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "内容不存在")
    return post


def _visible(post: Post, user: CurrentUser) -> bool:
    # 草稿只有提交人自己看得到
    return post.review_status != ReviewStatus.draft or post.created_by == user.id


def _get_editable(db: DbSession, user: CurrentUser, post_id: int, kind: str | None = None) -> Post:
    """没点过发布、或这一轮发布失败的内容可以修改和删除。失败的内容改完要重新审核、重新发布。"""
    post = _get_post(db, user, post_id, lock=True)
    if kind and (post.article is not None) != (kind == "article"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "内容不存在")
    if post.current_task and post.current_task.status != PublishStatus.failed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "已发布或正在发布的内容不能修改、删除")
    return post


def _submit_for_review(db: DbSession, post: Post, account: Account | None, draft: bool = False) -> PostOut:
    """新建或修改后存为草稿或回到待审核，上一轮的审核结果和发布任务（失败的）都清空，发布记录保留。"""
    post.account = account
    post.review_status = ReviewStatus.draft if draft else ReviewStatus.pending
    post.review_note = None
    post.reviewed_by = None
    post.reviewed_at = None
    post.current_task = None
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


def _video_cover(user: CurrentUser, url: str) -> str:
    """封面地址换成相对 media_dir 的路径；只能用本租户上传的图片。"""
    match = VIDEO_COVER_URL.fullmatch(url)
    if not match or match.group(2) != str(user.tenant_id) or not (Path(get_settings().media_dir) / match.group(1)).is_file():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "封面图片不存在，请重新上传")
    return match.group(1)


def _fill_video(post: Post, user: CurrentUser, account: Account | None, title: str, cover_url: str, options: str) -> None:
    """通用字段之外，按发布账号所在平台校验标题长度和专属配置。草稿没选账号时不能有专属配置。"""
    try:
        data = json.loads(options or "{}")
        parsed = video_options.parse(account.platform, data) if account else None
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "平台配置不正确，请刷新后重试") from None
    if parsed is None and data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先选择发布账号再填写平台配置")
    if account and len(title) > (title_max := video_options.TITLE_MAX[account.platform]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"该平台的标题最多 {title_max} 字")
    values = parsed.model_dump(exclude_none=True) if parsed else {}
    for key in (parsed.IMAGE_FIELDS if parsed else set()) & values.keys():
        values[key] = _video_cover(user, values[key])
    post.title = title
    post.cover_path = _video_cover(user, cover_url) if cover_url else None
    post.options = values


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


def _check_draft(post: Post, draft: bool) -> None:
    # 已提交的内容存草稿等于撤回审核，暂不支持
    if draft and post.review_status != ReviewStatus.draft:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "已提交的内容不能存为草稿")


def _remove_video(post: Post) -> None:
    if post.video_path:
        (Path(get_settings().media_dir) / post.video_path).unlink(missing_ok=True)


@router.post("/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    db: DbSession,
    user: CurrentUser,
    title: Annotated[str, Form(min_length=1, max_length=200)],
    category_id: Annotated[int, Form(description="必须是绑定了账号的分类，发到它绑定的账号")],
    description: Annotated[str, Form(max_length=1000)] = "",
    tags: Annotated[str, Form(description="逗号分隔的话题，不带 #")] = "",
    scheduled_at: Annotated[datetime | None, Form()] = None,
    video: Annotated[UploadFile | None, File()] = None,
    copy_from: Annotated[int | None, Form(description="复制这条内容的视频，不用重新上传")] = None,
    cover_url: Annotated[str, Form(description="竖封面，先传到 /api/video-covers；不传用平台自动生成的")] = "",
    options: Annotated[str, Form(description="平台专属配置 JSON，格式见 platforms/video_options.py")] = "{}",
    draft: Annotated[bool, Form(description="存草稿：只要求标题，其余提交审核时再校验")] = False,
) -> PostOut:
    """上传视频并提交审核（或存草稿）；审核通过后手动发布到分类绑定的账号。"""
    if video is not None and copy_from is not None or not draft and video is None and copy_from is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择视频")
    category = _new_post_category(db, user, category_id)
    account = _publish_account(db, user, category.account_id, tasks.VIDEO_PLATFORMS, "视频", draft)
    if not draft:
        _check_schedule(scheduled_at, account)
    post = Post(
        tenant_id=user.tenant_id,
        created_by=user.id,
        description=description,
        tags=[t.lstrip("#") for t in _split(tags)],
        scheduled_at=scheduled_at,
        category_id=category.id,
    )
    # 先校验完再存视频，校验不过不留下孤儿文件
    _fill_video(post, user, account, title, cover_url, options)
    if video is not None:
        post.video_path = _save_video(user, video)
    else:
        post.video_path = _copy_video(db, user, copy_from) if copy_from is not None else ""
    return _submit_for_review(db, post, account, draft)


@router.put("/posts/{post_id}", response_model=PostOut)
def update_post(
    post_id: int,
    db: DbSession,
    user: CurrentUser,
    title: Annotated[str, Form(min_length=1, max_length=200)],
    account_id: Annotated[int | None, Form(description="只有分类没绑定账号的老内容才用，见 _edit_account_id")] = None,
    description: Annotated[str, Form(max_length=1000)] = "",
    tags: Annotated[str, Form(description="逗号分隔的话题，不带 #")] = "",
    scheduled_at: Annotated[datetime | None, Form()] = None,
    video: Annotated[UploadFile | None, File(description="不传则沿用原视频")] = None,
    cover_url: Annotated[str, Form(description="不传则不用自定义封面")] = "",
    options: Annotated[str, Form()] = "{}",
    draft: Annotated[bool, Form(description="只有草稿能继续存草稿")] = False,
) -> PostOut:
    post = _get_editable(db, user, post_id, "video")
    _check_draft(post, draft)
    if not draft and video is None and not post.video_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择视频")
    account = _publish_account(db, user, _edit_account_id(post, account_id), tasks.VIDEO_PLATFORMS, "视频", draft)
    if not draft:
        _check_schedule(scheduled_at, account)
    _fill_video(post, user, account, title, cover_url, options)
    if video is not None:
        _remove_video(post)
        post.video_path = _save_video(user, video)
    post.description = description
    post.tags = [t.lstrip("#") for t in _split(tags)]
    post.scheduled_at = scheduled_at
    return _submit_for_review(db, post, account, draft)


@router.post("/video-covers", response_model=ImageOut, status_code=status.HTTP_201_CREATED)
def upload_video_cover(user: CurrentUser, image: Annotated[UploadFile, File()]) -> ImageOut:
    """上传视频封面，返回提交视频时用的地址。和图文图片一样不随内容删除：复制出来的内容引用同一张。"""
    suffix = Path(image.filename or "").suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "只支持 jpg / png 图片")
    data = image.file.read(VIDEO_COVER_MAX_BYTES + 1)
    if len(data) > VIDEO_COVER_MAX_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "封面不能超过 5MB")
    relative = Path("video-covers") / str(user.tenant_id) / f"{uuid.uuid4().hex}{suffix}"
    target = Path(get_settings().media_dir) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return ImageOut(url=f"/api/{relative}")


# 不校验登录：<img> 带不上令牌。文件名是随机 UUID，无法枚举
@router.get("/video-covers/{tenant_id}/{name}")
def video_cover(tenant_id: int, name: str) -> FileResponse:
    match = VIDEO_COVER_URL.fullmatch(f"/api/video-covers/{tenant_id}/{name}")
    if not match or not (path := Path(get_settings().media_dir) / match.group(1)).is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "图片不存在")
    return FileResponse(path)


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
    if not body.draft and not body.content.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请填写正文")
    if any(m.group(1) != str(user.tenant_id) for m in ARTICLE_IMAGE_URL.finditer(body.content)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "正文里有无法使用的图片")
    if body.draft and not body.cover_url:
        return ""
    # 只能引用本租户上传的图片
    cover = ARTICLE_IMAGE_URL.fullmatch(f'src="{body.cover_url}"')
    if not cover or cover.group(1) != str(user.tenant_id) or not article_image_path(*cover.groups()).is_file():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请上传封面")
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
    """提交图文审核（或存草稿）；审核通过后手动发布到分类绑定的公众号，draft_only 时只存公众号草稿箱。"""
    category = _new_post_category(db, user, body.category_id)
    account = _publish_account(db, user, category.account_id, tasks.ARTICLE_PLATFORMS, "图文", body.draft)
    if not body.draft:
        _check_schedule(body.scheduled_at, account)
    cover_path = _article_cover(body, user)
    post = Post(
        tenant_id=user.tenant_id,
        created_by=user.id,
        tags=[],
        video_path="",
        category_id=category.id,
    )
    _fill_article(post, body, cover_path)
    return _submit_for_review(db, post, account, body.draft)


@router.put("/articles/{post_id}", response_model=PostOut)
def update_article(post_id: int, body: ArticleIn, db: DbSession, user: CurrentUser) -> PostOut:
    post = _get_editable(db, user, post_id, "article")
    _check_draft(post, body.draft)
    account = _publish_account(db, user, _edit_account_id(post, body.account_id), tasks.ARTICLE_PLATFORMS, "图文", body.draft)
    if not body.draft:
        _check_schedule(body.scheduled_at, account)
    _fill_article(post, body, _article_cover(body, user))
    return _submit_for_review(db, post, account, body.draft)


# 内容列表的分组：草稿、待审核、已退回看审核状态；后面几个看这一轮的发布状态
ListStatus = Literal["draft", "pending", "rejected", "to_publish", "publishing", "scheduled", "published", "failed"]


def _visible_posts(user: CurrentUser):
    """本租户的内容，别人的草稿除外；外连当前发布任务（PublishTask），按发布状态筛选要用。"""
    return (
        select(Post)
        .outerjoin(PublishTask, Post.current_task_id == PublishTask.id)
        .where(Post.tenant_id == user.tenant_id, or_(Post.review_status != ReviewStatus.draft, Post.created_by == user.id))
    )


def _status_filter(status_: str, now: datetime):
    """status 按「要谁处理」分组，和 _publish_status 的结果一一对应（已存草稿算已发布）。"""
    task = PublishTask
    if status_ in ("draft", "pending", "rejected"):
        return Post.review_status == status_
    if status_ == "to_publish":
        return and_(Post.review_status == ReviewStatus.approved, Post.current_task_id.is_(None))
    if status_ == "publishing":
        return task.status.in_([PublishStatus.queued, PublishStatus.running])
    if status_ == "scheduled":
        return or_(task.status == PublishStatus.scheduled, and_(task.status == PublishStatus.success, Post.scheduled_at > now))
    if status_ == "published":
        return and_(task.status == PublishStatus.success, or_(Post.scheduled_at.is_(None), Post.scheduled_at <= now))
    return task.status == PublishStatus.failed


def _scope_filters(query, db: DbSession, user: CurrentUser, category_id: int | None):
    if category_id is not None:
        query = query.where(Post.category_id.in_(subtree_ids(db, user, category_id)))
    return query


@router.get("/posts", response_model=list[PostOut])
def list_posts(
    db: DbSession,
    user: CurrentUser,
    status_: Annotated[ListStatus | None, Query(alias="status")] = None,
    category_id: int | None = None,
    limit: int = 100,
) -> list[PostOut]:
    """status 按「要谁处理」分组，见 ListStatus；category_id 包含下级分类；未分类的老内容只在不传 category_id 时出现。"""
    query = _scope_filters(_visible_posts(user), db, user, category_id)
    if status_:
        query = query.where(_status_filter(status_, datetime.now(UTC)))
    rows = db.scalars(
        query.options(
            selectinload(Post.article),
            selectinload(Post.account),
            selectinload(Post.creator),
            selectinload(Post.reviewer),
            selectinload(Post.current_task).selectinload(PublishTask.result),
        )
        .order_by(Post.id.desc())
        .limit(min(limit, 500))
    ).all()
    return [_post_out(post) for post in rows]


# 要放在 /posts/{post_id} 前面，否则 counts 会被当成 id
@router.get("/posts/counts", response_model=dict[str, int])
def count_posts(
    db: DbSession,
    user: CurrentUser,
    category_id: int | None = None,
) -> dict[str, int]:
    """各状态分组的条数（筛选条件和列表相同），all 是全部。一次查询用 FILTER 统计所有分组。"""
    now = datetime.now(UTC)
    groups = get_args(ListStatus)
    columns = [func.count().filter(_status_filter(name, now)).label(name) for name in groups]
    query = _scope_filters(_visible_posts(user), db, user, category_id).with_only_columns(
        func.count().label("all"), *columns
    )
    return dict(db.execute(query).one()._mapping)


@router.get("/posts/{post_id}/tasks", response_model=list[PublishTaskOut])
def list_post_tasks(post_id: int, db: DbSession, user: CurrentUser) -> list[PublishTaskOut]:
    """这条内容的发布记录，新的在前；修改前失败的旧任务也在里面（不能再重试）。"""
    post = _get_post(db, user, post_id)
    rows = db.scalars(
        select(PublishTask)
        .where(PublishTask.post_id == post.id)
        .options(selectinload(PublishTask.post), selectinload(PublishTask.result))
        .order_by(PublishTask.id.desc())
    ).all()
    return [_task_out(task) for task in rows]


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
    # 锁住内容，重复点击时第二次能看到已经有发布任务
    post = _get_post(db, user, post_id, lock=True)
    if post.review_status != ReviewStatus.approved:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "只有审核通过的内容可以发布")
    if post.current_task_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "这条内容已经发布过了")
    if post.article:
        account = _publish_account(db, user, post.account_id, tasks.ARTICLE_PLATFORMS, "图文")
    else:
        account = _publish_account(db, user, post.account_id, tasks.VIDEO_PLATFORMS, "视频")
    _check_schedule(body.scheduled_at, account)
    post.scheduled_at = body.scheduled_at
    return _create_task(db, user, post, account)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int, db: DbSession, user: CurrentUser) -> None:
    post = _get_editable(db, user, post_id)
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
    # 和修改内容互斥：修改时也锁这一行，改完 current_task 就不再是这个任务
    post = db.get(Post, task.post_id, with_for_update=True)
    if post.current_task_id != task.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "内容已修改，请重新审核后再发布")
    claimed = db.execute(
        update(PublishTask)
        .where(PublishTask.id == task.id, PublishTask.status == PublishStatus.failed)
        .values(status=PublishStatus.queued, error=None, finished_at=None)
    ).rowcount
    if not claimed:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "只有失败的任务可以重试")
    db.commit()
    db.refresh(task)
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
