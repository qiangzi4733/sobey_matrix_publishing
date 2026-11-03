from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import AccountStatus, Platform, PublishStatus, ReviewStatus, UserRole


class RegisterIn(BaseModel):
    company_name: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: UserRole
    tenant_id: int
    tenant_name: str


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: Platform
    external_id: str
    display_name: str
    avatar_url: str | None
    status: AccountStatus
    last_checked_at: datetime | None
    created_at: datetime


class AccountUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


class AccountUsageOut(BaseModel):
    """移除账号前给客户看的影响范围。"""

    posts: int  # 选了这个账号、还没点发布的内容
    pending_tasks: int  # 排队中、等定时的发布任务，移除后会标为失败
    running_tasks: int  # 正在发布，有的话不能移除


class LoginStartOut(BaseModel):
    login_id: str


class CodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=8, pattern=r"^\d+$")


class VerificationOut(BaseModel):
    message: str
    image: str | None


class LoginStatusOut(BaseModel):
    # starting / waiting / scanned / need_code / verifying / success / failed
    status: str
    message: str
    qr: str | None = None
    account_id: int | None = None


class PublishTaskOut(BaseModel):
    id: int
    post_id: int
    title: str
    account_id: int | None
    account_name: str
    platform: Platform
    status: PublishStatus
    error: str | None
    has_screenshot: bool
    # 公众号：文章链接；只存了草稿时 draft 为 true
    url: str | None = None
    draft: bool = False
    # 发布中平台要求短信验证码，等客户输入
    needs_code: bool = False
    scheduled_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class PostAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: Platform
    display_name: str
    status: AccountStatus


class PostOut(BaseModel):
    id: int
    kind: str  # video / article
    title: str
    review_status: ReviewStatus
    review_note: str | None
    reviewer_name: str | None
    reviewed_at: datetime | None
    creator_name: str | None
    # 已被移除的账号不在这里
    accounts: list[PostAccountOut]
    scheduled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PostDetailOut(PostOut):
    description: str
    tags: list[str]
    video_url: str | None = None
    author: str = ""
    content: str = ""
    cover_url: str = ""
    source_url: str = ""
    open_comment: bool = False
    draft_only: bool = True


class RejectIn(BaseModel):
    note: str = Field(min_length=1, max_length=500)


class PublishIn(BaseModel):
    # 发布时可以改定时：审核期间原定时间可能已过或超出平台允许的范围
    scheduled_at: datetime | None = None


class ImageOut(BaseModel):
    url: str


class ArticleIn(BaseModel):
    # 长度限制按公众号草稿接口的要求
    title: str = Field(min_length=1, max_length=64)
    author: str = Field(default="", max_length=16)
    digest: str = Field(default="", max_length=120)
    content: str = Field(min_length=1, max_length=200_000)
    cover_url: str
    source_url: str = Field(default="", max_length=500, pattern=r"^(https?://.*)?$")
    open_comment: bool = False
    draft_only: bool = True
    account_ids: list[int] = Field(min_length=1)
    scheduled_at: datetime | None = None


class WechatAuthorizeOut(BaseModel):
    url: str


class WechatCallbackIn(BaseModel):
    state: str
    auth_code: str = Field(min_length=1, max_length=512)
