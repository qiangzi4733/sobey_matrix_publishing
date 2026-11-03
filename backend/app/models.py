import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Platform(str, enum.Enum):
    wechat_mp = "wechat_mp"  # 微信公众号（开放平台第三方授权）
    kuaishou = "kuaishou"  # 快手（OAuth 授权）
    douyin = "douyin"  # 抖音（扫码登录 + 浏览器自动化）
    channels = "channels"  # 微信视频号（扫码登录 + 浏览器自动化）


class AccountStatus(str, enum.Enum):
    active = "active"
    expired = "expired"  # 授权或登录失效，需要客户重新授权/扫码
    error = "error"


class PublishStatus(str, enum.Enum):
    scheduled = "scheduled"  # 等到 scheduled_at 再入队
    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"


class ReviewStatus(str, enum.Enum):
    pending = "pending"  # 待审核
    rejected = "rejected"  # 已退回，可修改后重新提交
    approved = "approved"  # 审核通过，等人手动点发布
    published = "published"  # 已点发布，按账号生成了 PublishTask


class UserRole(str, enum.Enum):
    owner = "owner"
    member = "member"


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Tenant(Timestamped, Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

    users: Mapped[list["User"]] = relationship(back_populates="tenant")


class User(Timestamped, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False), default=UserRole.member)

    tenant: Mapped[Tenant] = relationship(back_populates="users")


class Account(Timestamped, Base):
    """客户名下的一个矩阵账号。"""

    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "platform", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform, native_enum=False))
    # 平台侧唯一标识：公众号 authorizer_appid、快手 open_id、抖音/视频号的账号 ID
    external_id: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, native_enum=False), default=AccountStatus.active
    )
    # 加密后的凭证 JSON（refresh_token / cookie storage_state 等），见 app.security
    credentials_encrypted: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Post(Timestamped, Base):
    """一次发布的内容，可以同时发到多个账号（每个账号一条 PublishTask）。"""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    # 相对 media_dir 的路径；图文为空字符串（正文在 Article）
    video_path: Mapped[str] = mapped_column(String(500))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 引入审核前的内容都是直接发布的，所以已有行默认 published
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, native_enum=False, length=20), index=True, server_default=ReviewStatus.published.value
    )
    # 提交时选的账号，点发布时才生成 PublishTask
    account_ids: Mapped[list[int]] = mapped_column(JSON, server_default="[]")
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tasks: Mapped[list["PublishTask"]] = relationship(back_populates="post")
    # 正文跟着内容一起删（删除未发布的内容时）
    article: Mapped["Article | None"] = relationship(cascade="all, delete-orphan")
    creator: Mapped["User | None"] = relationship(foreign_keys=[created_by])
    reviewer: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by])


class Article(Base):
    """公众号图文的正文部分，标题、摘要（description）、定时沿用 Post。
    单独建表是当时还没有 Alembic，不能给已有的 posts 表加字段。"""

    __tablename__ = "articles"

    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    author: Mapped[str] = mapped_column(String(16), default="")
    # HTML，图片引用本平台的 /api/article-images/ 地址，发布时再转传微信
    content: Mapped[str] = mapped_column(Text)
    # 相对 media_dir 的路径
    cover_path: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str] = mapped_column(String(500), default="")
    open_comment: Mapped[bool] = mapped_column(Boolean, default=False)
    # 只存草稿箱，不发表（发表后对外可见）
    draft_only: Mapped[bool] = mapped_column(Boolean, default=True)


class PublishTask(Timestamped, Base):
    __tablename__ = "publish_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    # 账号被移除后保留发布记录
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    account_name: Mapped[str] = mapped_column(String(100))
    platform: Mapped[Platform] = mapped_column(Enum(Platform, native_enum=False))
    status: Mapped[PublishStatus] = mapped_column(Enum(PublishStatus, native_enum=False), index=True)
    error: Mapped[str | None] = mapped_column(Text)
    # 失败现场截图，相对 debug_dir
    screenshot_path: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    post: Mapped[Post] = relationship(back_populates="tasks")
    account: Mapped[Account | None] = relationship()
    result: Mapped["PublishResult | None"] = relationship()


class PublishResult(Base):
    """发布成功后平台返回的信息，如公众号的草稿 media_id、文章链接。"""

    __tablename__ = "publish_results"

    task_id: Mapped[int] = mapped_column(ForeignKey("publish_tasks.id", ondelete="CASCADE"), primary_key=True)
    url: Mapped[str | None] = mapped_column(String(1000))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
