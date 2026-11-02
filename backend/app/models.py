import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
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
    # 相对 media_dir 的路径
    video_path: Mapped[str] = mapped_column(String(500))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tasks: Mapped[list["PublishTask"]] = relationship(back_populates="post")


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
