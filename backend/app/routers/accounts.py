from celery.exceptions import TimeoutError as CeleryTimeout
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app import login_sessions, tasks, verification
from app.deps import CurrentUser, DbSession
from app.models import Account, Platform
from app.schemas import AccountOut, AccountUpdate, CodeIn, LoginStartOut, LoginStatusOut

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _get_owned(db: DbSession, user: CurrentUser, account_id: int) -> Account:
    account = db.get(Account, account_id)
    # 其他租户的账号一律当作不存在，避免泄露
    if account is None or account.tenant_id != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    return account


@router.get("", response_model=list[AccountOut])
def list_accounts(db: DbSession, user: CurrentUser, platform: Platform | None = None) -> list[Account]:
    query = select(Account).where(Account.tenant_id == user.tenant_id).order_by(Account.id)
    if platform:
        query = query.where(Account.platform == platform)
    return list(db.scalars(query))


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(account_id: int, body: AccountUpdate, db: DbSession, user: CurrentUser) -> Account:
    account = _get_owned(db, user, account_id)
    account.display_name = body.display_name
    db.commit()
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, db: DbSession, user: CurrentUser) -> None:
    db.delete(_get_owned(db, user, account_id))
    db.commit()


@router.post("/{account_id}/check", response_model=AccountOut)
def check_account(account_id: int, db: DbSession, user: CurrentUser) -> Account:
    """立即检测登录状态（同步等待浏览器检测结果）。"""
    account = _get_owned(db, user, account_id)
    if account.platform not in tasks.BROWSER_PLATFORMS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该平台不需要检测登录状态")
    result = tasks.check_account.apply_async(args=[account.id], queue=tasks.BROWSER_QUEUE)
    try:
        if result.get(timeout=150) == "error":
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "检测时访问平台出错，请稍后再试")
    except CeleryTimeout:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "检测超时，请稍后再试") from None
    db.refresh(account)
    return account


@router.post("/login/{platform}", response_model=LoginStartOut)
def start_login(platform: Platform, user: CurrentUser) -> LoginStartOut:
    """开始扫码登录。重新登录已有账号也走这里，扫码后按平台账号 ID 自动更新。"""
    if platform not in tasks.BROWSER_PLATFORMS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该平台不支持扫码登录")
    login_id = login_sessions.create(user.tenant_id, platform.value)
    tasks.qr_login.apply_async(args=[login_id], queue=tasks.BROWSER_QUEUE)
    return LoginStartOut(login_id=login_id)


def _owned_session(login_id: str, user: CurrentUser) -> dict:
    session = login_sessions.get(login_id)
    if session is None or session["tenant_id"] != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "登录会话不存在或已过期")
    return session


@router.get("/login/sessions/{login_id}", response_model=LoginStatusOut)
def login_status(login_id: str, user: CurrentUser) -> LoginStatusOut:
    session = _owned_session(login_id, user)
    # 平台要求短信验证时，把验证弹窗截图代替二维码给前端展示
    if pending := verification.pending(f"login:{login_id}"):
        session.update(status="need_code", message=pending["message"], qr=pending["image"])
    return LoginStatusOut(**session)


@router.post("/login/sessions/{login_id}/code", status_code=status.HTTP_204_NO_CONTENT)
def submit_login_code(login_id: str, body: CodeIn, user: CurrentUser) -> None:
    _owned_session(login_id, user)
    if not verification.submit(f"login:{login_id}", body.code):
        raise HTTPException(status.HTTP_409_CONFLICT, "当前不需要验证码")
    login_sessions.update(login_id, status="verifying", message="验证码已提交，正在验证")
