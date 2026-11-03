"""本地开发用的「微信开放平台」模拟（WECHAT_MP_MOCK=true 时才挂载）。

本地没有公网 HTTPS 域名：收不到 ticket 推送，授权页也只能从登记过的域名打开，第三方平台流程没法真实跑。
这里按官方接口格式模拟第三方平台这一侧：ticket 推送（加密后打到我们自己的事件接收接口）、
component_access_token、预授权码、授权确认页、auth_code 换授权信息。
授权方的 access_token 用测试公众号的 AppID/AppSecret 向微信真实换取，之后的草稿、发表都是真实接口。
"""

import html
import secrets
import time
from typing import Annotated, Any

import httpx
import redis
from fastapi import APIRouter, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import get_settings
from app.platforms import wechat_crypto

router = APIRouter(prefix="/api/mock-wx", tags=["mock-wechat"], include_in_schema=False)

_redis = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _key(*parts: str) -> str:
    return "mockwx:" + ":".join(parts)


def _err(errcode: int, errmsg: str) -> dict[str, Any]:
    return {"errcode": errcode, "errmsg": errmsg}


def _new(kind: str, ttl: int | None, value: str = "1") -> str:
    token = secrets.token_urlsafe(24)
    _redis.set(_key(kind, token), value, ex=ttl)
    return token


def _real_access_token() -> tuple[str, int]:
    settings = get_settings()
    data = httpx.post(
        "https://api.weixin.qq.com/cgi-bin/stable_token",
        json={
            "grant_type": "client_credential",
            "appid": settings.wechat_mp_mock_appid,
            "secret": settings.wechat_mp_mock_appsecret,
        },
        timeout=15,
    ).json()
    if "access_token" not in data:
        raise HTTPException(502, f"测试公众号换取 access_token 失败：{data}")
    return data["access_token"], data["expires_in"]


def _valid_component_token(token: str) -> bool:
    return bool(_redis.exists(_key("component_token", token)))


# ---------- 推送 ----------


def _push(xml_fields: dict[str, str]) -> None:
    settings = get_settings()
    inner = "".join(f"<{k}><![CDATA[{v}]]></{k}>" for k, v in xml_fields.items())
    encrypted = wechat_crypto.encrypt(f"<xml>{inner}</xml>")
    timestamp, nonce = str(int(time.time())), secrets.token_hex(8)
    params = {
        "timestamp": timestamp,
        "nonce": nonce,
        "encrypt_type": "aes",
        "msg_signature": wechat_crypto.signature(timestamp, nonce, encrypted),
    }
    body = f"<xml><AppId><![CDATA[{settings.wechat_component_appid}]]></AppId><Encrypt><![CDATA[{encrypted}]]></Encrypt></xml>"
    resp = httpx.post(f"{settings.internal_backend_url}/api/wechat-mp/events", params=params, content=body, timeout=15)
    if resp.text != "success":
        raise HTTPException(502, f"事件接收接口返回 {resp.status_code}：{resp.text}")


@router.post("/push-ticket")
def push_ticket() -> dict[str, str]:
    ticket = "ticket@@@" + secrets.token_urlsafe(32)
    _redis.set(_key("ticket"), ticket, ex=12 * 3600)
    _push(
        {
            "AppId": get_settings().wechat_component_appid,
            "CreateTime": str(int(time.time())),
            "InfoType": "component_verify_ticket",
            "ComponentVerifyTicket": ticket,
        }
    )
    return {"status": "pushed"}


@router.post("/push-unauthorized")
def push_unauthorized() -> dict[str, str]:
    """模拟客户在公众号后台取消授权。"""
    settings = get_settings()
    for key in _redis.scan_iter(_key("refresh_token", "*")):
        _redis.delete(key)
    _push(
        {
            "AppId": settings.wechat_component_appid,
            "CreateTime": str(int(time.time())),
            "InfoType": "unauthorized",
            "AuthorizerAppid": settings.wechat_mp_mock_appid,
        }
    )
    return {"status": "pushed"}


# ---------- 第三方平台接口 ----------


@router.post("/cgi-bin/component/api_component_token")
def api_component_token(body: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if body.get("component_appid") != settings.wechat_component_appid or body.get(
        "component_appsecret"
    ) != settings.wechat_component_appsecret:
        return _err(40013, "invalid appid or appsecret")
    if not body.get("component_verify_ticket") or body["component_verify_ticket"] != _redis.get(_key("ticket")):
        return _err(61006, "component ticket is invalid")
    return {"component_access_token": _new("component_token", 7200), "expires_in": 7200}


@router.post("/cgi-bin/component/api_create_preauthcode")
def api_create_preauthcode(component_access_token: Annotated[str, Query()]) -> dict[str, Any]:
    if not _valid_component_token(component_access_token):
        return _err(40001, "invalid component_access_token")
    return {"pre_auth_code": _new("pre_auth_code", 1800), "expires_in": 1800}


@router.get("/cgi-bin/componentloginpage", response_class=HTMLResponse)
def login_page(pre_auth_code: str, redirect_uri: str, component_appid: str = "", auth_type: int = 1) -> str:
    if not _redis.exists(_key("pre_auth_code", pre_auth_code)):
        return "<h3>预授权码无效或已过期，请回到平台重新发起授权</h3>"
    name = html.escape(get_settings().wechat_mp_mock_name)
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>公众号授权（本地模拟）</title>
<style>body{{font-family:sans-serif;max-width:480px;margin:60px auto;padding:0 16px;color:#333}}
.box{{border:1px solid #ddd;border-radius:8px;padding:24px}}.warn{{color:#b26a00;font-size:13px}}
button{{background:#07c160;color:#fff;border:0;border-radius:4px;padding:10px 28px;font-size:15px;cursor:pointer}}
li{{margin:4px 0}}</style></head><body><div class="box">
<p class="warn">本地开发模拟页面。真实环境这里是微信的授权页，由公众号管理员扫码确认。</p>
<h3>授权公众号「{name}」给第三方平台</h3>
<p>将授予以下权限：</p><ul><li>素材管理</li><li>草稿箱与发表</li><li>账号基础信息</li></ul>
<form method="post" action="/api/mock-wx/cgi-bin/componentloginpage/confirm">
<input type="hidden" name="pre_auth_code" value="{html.escape(pre_auth_code)}">
<input type="hidden" name="redirect_uri" value="{html.escape(redirect_uri)}">
<button type="submit">确认授权</button></form></div></body></html>"""


@router.post("/cgi-bin/componentloginpage/confirm")
def confirm_login(pre_auth_code: Annotated[str, Form()], redirect_uri: Annotated[str, Form()]) -> RedirectResponse:
    # 预授权码一次有效；只允许跳回本平台，避免变成开放跳转
    if not redirect_uri.startswith(get_settings().public_base_url + "/"):
        raise HTTPException(400, "回调地址不在授权发起页域名下")
    if not _redis.delete(_key("pre_auth_code", pre_auth_code)):
        raise HTTPException(400, "预授权码无效或已过期")
    auth_code = "queryauthcode@@@" + _new("auth_code", 3600)
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}auth_code={auth_code}&expires_in=3600", status_code=302)


@router.post("/cgi-bin/component/api_query_auth")
def api_query_auth(component_access_token: Annotated[str, Query()], body: dict[str, Any]) -> dict[str, Any]:
    if not _valid_component_token(component_access_token):
        return _err(40001, "invalid component_access_token")
    code = str(body.get("authorization_code", "")).removeprefix("queryauthcode@@@")
    if not _redis.delete(_key("auth_code", code)):
        return _err(61010, "code is expired")
    token, expires_in = _real_access_token()
    return {
        "authorization_info": {
            "authorizer_appid": get_settings().wechat_mp_mock_appid,
            "authorizer_access_token": token,
            "expires_in": expires_in,
            "authorizer_refresh_token": "refreshtoken@@@" + _new("refresh_token", None),
            # 1 消息管理、11 素材管理、7 群发与通知（草稿、发表在此权限集）
            "func_info": [{"funcscope_category": {"id": i}} for i in (1, 7, 11)],
        }
    }


@router.post("/cgi-bin/component/api_authorizer_token")
def api_authorizer_token(component_access_token: Annotated[str, Query()], body: dict[str, Any]) -> dict[str, Any]:
    if not _valid_component_token(component_access_token):
        return _err(40001, "invalid component_access_token")
    refresh = str(body.get("authorizer_refresh_token", "")).removeprefix("refreshtoken@@@")
    if body.get("authorizer_appid") != get_settings().wechat_mp_mock_appid or not _redis.exists(
        _key("refresh_token", refresh)
    ):
        return _err(61023, "refresh_token is invalid")
    token, expires_in = _real_access_token()
    return {
        "authorizer_access_token": token,
        "expires_in": expires_in,
        "authorizer_refresh_token": body["authorizer_refresh_token"],
    }


@router.post("/cgi-bin/component/api_get_authorizer_info")
def api_get_authorizer_info(component_access_token: Annotated[str, Query()], body: dict[str, Any]) -> dict[str, Any]:
    if not _valid_component_token(component_access_token):
        return _err(40001, "invalid component_access_token")
    settings = get_settings()
    if body.get("authorizer_appid") != settings.wechat_mp_mock_appid:
        return _err(61003, "component is not authorized by this account")
    return {
        "authorizer_info": {
            "nick_name": settings.wechat_mp_mock_name,
            "head_img": "",
            # 2 服务号；0 微信认证
            "service_type_info": {"id": 2},
            "verify_type_info": {"id": 0},
            "user_name": "gh_mock",
            "alias": settings.wechat_mp_mock_name,
        },
        "authorization_info": {"authorizer_appid": settings.wechat_mp_mock_appid},
    }
