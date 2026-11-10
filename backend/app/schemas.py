from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.models import AccountStatus, Platform, PublishStatus, ReviewStatus, UserRole


class RegisterIn(BaseModel):
    company_name: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    # 登录页叫「用户名」，目前用户名就是邮箱；不按邮箱格式校验，输错时统一提示用户名或密码错误
    email: str
    password: str
    captcha_id: str
    captcha_code: str


class CaptchaOut(BaseModel):
    captcha_id: str
    svg: str


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


class AccountUsageOut(BaseModel):
    """移除账号前给客户看的影响范围。"""

    posts: int  # 发到这个账号、还没点发布的内容
    pending_tasks: int  # 排队中、等定时的发布任务，移除后会标为失败
    running_tasks: int  # 正在发布，有的话不能移除
    categories: int  # 绑定了这个账号的分类，移除后要重新绑定


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
    can_retry: bool = False
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
    # 这一轮的发布状态：publishing / scheduled / success / draft_saved（公众号只存了草稿）/ failed；没点发布为空
    publish_status: str | None
    review_note: str | None
    reviewer_name: str | None
    reviewed_at: datetime | None
    creator_name: str | None
    # 账号被移除后为空
    account: PostAccountOut | None
    # 发布任务记下的账号名，账号被移除后显示用
    account_name: str | None
    # 为空是未分类；前端按分类列表拼出完整路径
    category_id: int | None
    scheduled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # 视频的竖封面或图文封面，列表里做缩略图；视频没传封面时为空
    cover_url: str = ""


class PostDetailOut(PostOut):
    description: str
    tags: list[str]
    video_url: str | None = None
    # 视频：发布平台专属配置，图片字段是地址
    options: dict = {}
    author: str = ""
    content: str = ""
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
    # 存草稿时正文、封面、公众号都可以先不填
    content: str = Field(default="", max_length=200_000)
    cover_url: str = ""
    source_url: str = Field(default="", max_length=500, pattern=r"^(https?://.*)?$")
    open_comment: bool = False
    draft_only: bool = True
    # 新建时必填，必须是绑定了公众号的分类；修改时不能改分类，忽略
    category_id: int | None = None
    # 只有分类没绑定账号的老内容修改时才用，见 posts._edit_account_id
    account_id: int | None = None
    scheduled_at: datetime | None = None
    draft: bool = False


class CategoryIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    parent_id: int | None = None
    # 绑定的发布账号，不绑定为空
    account_id: int | None = None


class CategoryOut(BaseModel):
    id: int
    parent_id: int | None
    name: str
    account: PostAccountOut | None
    # 直接挂在这个分类下的内容数（不含子分类）
    post_count: int
    created_at: datetime


class WechatAuthorizeOut(BaseModel):
    url: str


class WechatCallbackIn(BaseModel):
    state: str
    auth_code: str = Field(min_length=1, max_length=512)
