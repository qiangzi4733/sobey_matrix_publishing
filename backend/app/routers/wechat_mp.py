import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, update

from app import login_sessions
from app.config import get_settings
from app.deps import CurrentUser, DbSession
from app.models import Account, AccountStatus, Platform
from app.platforms import wechat_crypto, wechat_mp
from app.platforms.base import PublishError
from app.schemas import AccountOut, WechatAuthorizeOut, WechatCallbackIn
from app.security import encrypt_credentials

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wechat-mp", tags=["wechat_mp"])


def _wechat_errors(func):
    """把微信接口错误转成 502，提示信息给前端展示。"""

    def call(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (PublishError, wechat_mp.WechatError) as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None

    return call


@router.post("/authorize", response_model=WechatAuthorizeOut)
def start_authorize(user: CurrentUser) -> WechatAuthorizeOut:
    """生成授权页地址。授权完成后微信把浏览器跳回前端回调页，前端再调 /callback。"""
    # 复用扫码登录会话作为 state，把回调和发起授权的租户绑定起来
    state = login_sessions.create(user.tenant_id, Platform.wechat_mp.value)
    redirect_uri = f"{get_settings().public_base_url}/accounts/wechat-mp/callback?state={state}"
    url = _wechat_errors(wechat_mp.authorize_url)(redirect_uri)
    return WechatAuthorizeOut(url=url)


@router.post("/callback", response_model=AccountOut)
def finish_authorize(body: WechatCallbackIn, db: DbSession, user: CurrentUser) -> Account:
    session = login_sessions.get(body.state)
    if session is None or session["tenant_id"] != user.tenant_id or session["platform"] != Platform.wechat_mp.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "授权会话不存在或已过期，请重新发起授权")
    if session["status"] == "success":
        raise HTTPException(status.HTTP_409_CONFLICT, "该授权已完成")

    credentials, profile = _wechat_errors(wechat_mp.authorize)(body.auth_code)
    account = db.scalar(
        select(Account).where(
            Account.tenant_id == user.tenant_id,
            Account.platform == Platform.wechat_mp,
            Account.external_id == profile["external_id"],
        )
    )
    if account is None:
        account = Account(tenant_id=user.tenant_id, platform=Platform.wechat_mp, external_id=profile["external_id"])
        db.add(account)
    # 名称、头像以平台为准，重新授权时同步
    account.display_name = profile["nickname"] or account.display_name or profile["external_id"]
    account.avatar_url = profile["avatar_url"] or account.avatar_url
    account.credentials_encrypted = encrypt_credentials(credentials)
    account.status = AccountStatus.active
    account.last_checked_at = datetime.now(UTC)
    db.commit()
    login_sessions.update(body.state, status="success", account_id=account.id)
    return account


@router.post("/events", response_class=PlainTextResponse)
async def component_events(
    request: Request,
    db: DbSession,
    timestamp: Annotated[str, Query()],
    nonce: Annotated[str, Query()],
    msg_signature: Annotated[str, Query()],
) -> str:
    """开放平台「授权事件接收 URL」：ticket 推送、取消授权等。微信要求返回 success。"""
    try:
        event = wechat_crypto.parse_push(await request.body(), timestamp, nonce, msg_signature)
    except Exception:
        log.warning("无法解析的开放平台推送", exc_info=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid") from None

    info_type = event.get("InfoType")
    if info_type == "component_verify_ticket":
        wechat_mp.save_ticket(event["ComponentVerifyTicket"])
    elif info_type == "unauthorized":
        # 客户在公众号后台取消了授权：所有租户下的这个公众号都标记失效
        appid = event["AuthorizerAppid"]
        wechat_mp.mark_unauthorized(appid)
        db.execute(
            update(Account)
            .where(Account.platform == Platform.wechat_mp, Account.external_id == appid)
            .values(status=AccountStatus.expired)
        )
        db.commit()
    # authorized / updateauthorized 以浏览器回调为准，这里不处理
    return "success"
