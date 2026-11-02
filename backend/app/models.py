import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
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
