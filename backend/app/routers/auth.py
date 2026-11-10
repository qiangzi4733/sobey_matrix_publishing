from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app import captcha
from app.deps import CurrentUser, DbSession
from app.models import Tenant, User, UserRole
from app.schemas import CaptchaOut, LoginIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        tenant_id=user.tenant_id,
        tenant_name=user.tenant.name,
    )


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: DbSession) -> TokenOut:
    """客户注册：同时创建租户（公司）和所有者账号。"""
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")

    tenant = Tenant(name=body.company_name)
    user = User(
        tenant=tenant,
        email=email,
        name=body.name,
        password_hash=hash_password(body.password),
        role=UserRole.owner,
    )
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/captcha", response_model=CaptchaOut)
def get_captcha() -> CaptchaOut:
    captcha_id, svg = captcha.create()
    return CaptchaOut(captcha_id=captcha_id, svg=svg)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: DbSession) -> TokenOut:
    # 先核验证码再查密码，验证码不对时不暴露账号是否存在
    if not captcha.verify(body.captcha_id, body.captcha_code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误或已过期")
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return _user_out(user)
