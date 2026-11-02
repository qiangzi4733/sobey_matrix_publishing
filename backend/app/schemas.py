from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import AccountStatus, Platform, PublishStatus, UserRole


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


class LoginStartOut(BaseModel):
    login_id: str


class LoginStatusOut(BaseModel):
    # starting / waiting / scanned / verifying / success / failed
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
    scheduled_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
