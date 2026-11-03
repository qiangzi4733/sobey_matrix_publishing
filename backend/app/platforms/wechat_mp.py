"""微信公众号：开放平台第三方平台授权 + 草稿箱 / 发表接口（官方 API，不需要浏览器）。

授权流程：微信每 10 分钟推送 component_verify_ticket → 换 component_access_token → 预授权码 →
客户在授权页确认 → 回调带 auth_code → 换 authorizer_refresh_token（加密存库，长期有效）。
发布时用 refresh_token 换 2 小时有效的 authorizer_access_token（缓存在 Redis）。

开启 WECHAT_MP_MOCK 时第三方平台接口改调 backend 自己的模拟实现（app.mock_wechat），其余代码路径不变。
"""

import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import redis

from app.config import get_settings
from app.platforms.base import LoginExpired, PublishError

API = "https://api.weixin.qq.com"
LOGIN_PAGE = "https://mp.weixin.qq.com/cgi-bin/componentloginpage"
MOCK_PREFIX = "/api/mock-wx"

TICKET_KEY = "wechat:component_verify_ticket"
COMPONENT_TOKEN_KEY = "wechat:component_access_token"

# 授权已失效（refresh_token 无效、客户已取消授权）
EXPIRED_CODES = {61003, 61023}
# access_token 失效，丢掉缓存重新换一次
TOKEN_INVALID_CODES = {40001, 40014, 42001}
ERROR_HINTS = {
    48001: "公众号没有该接口权限（需要已认证的公众号，并在授权时勾选相应权限）",
    45009: "接口调用次数已达今日上限",
    53503: "草稿未通过发布检查",
    53504: "需前往公众号后台完成发表",
    53505: "请手动保存成功后再发表",
}

# 正文图片（只支持 jpg/png，单张 1MB 内）和封面都先传到本平台，再由 worker 转传给微信
ARTICLE_IMAGE_URL = re.compile(r'src="[^"]*?/api/article-images/(\d+)/([0-9a-f]{32}\.(?:jpg|jpeg|png))"')

_redis = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


class WechatError(Exception):
    def __init__(self, errcode: int, errmsg: str):
        super().__init__(f"{ERROR_HINTS.get(errcode, errmsg)}（错误码 {errcode}）")
        self.errcode = errcode


def article_image_path(tenant_id: int | str, name: str) -> Path:
    return Path(get_settings().media_dir) / "article-images" / str(tenant_id) / name


def _component_api() -> str:
    settings = get_settings()
    return settings.internal_backend_url + MOCK_PREFIX if settings.wechat_mp_mock else API


def _check(resp: httpx.Response) -> dict[str, Any]:
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode"):
        raise WechatError(data["errcode"], data.get("errmsg", ""))
    return data


def _post(url: str, body: dict[str, Any], **params: str) -> dict[str, Any]:
    # 必须 ensure_ascii=False：中文被转成 \uXXXX 后，微信会原样显示在标题、正文里
    content = json.dumps(body, ensure_ascii=False).encode()
    headers = {"Content-Type": "application/json; charset=utf-8"}
    return _check(httpx.post(url, params=params, content=content, headers=headers, timeout=30))


def _upload(url: str, path: Path, **params: str) -> dict[str, Any]:
    with path.open("rb") as f:
        return _check(httpx.post(url, params=params, files={"media": (path.name, f)}, timeout=120))


# ---------- 第三方平台 ----------


def save_ticket(ticket: str) -> None:
    # ticket 每 10 分钟推送一次，有效期 12 小时
    _redis.set(TICKET_KEY, ticket, ex=12 * 3600)


def _component_token() -> str:
    if token := _redis.get(COMPONENT_TOKEN_KEY):
        return token
    ticket = _redis.get(TICKET_KEY)
    if not ticket:
        raise PublishError("尚未收到微信推送的 component_verify_ticket，请稍后再试（每 10 分钟推送一次）")
    settings = get_settings()
    data = _post(
        f"{_component_api()}/cgi-bin/component/api_component_token",
        {
            "component_appid": settings.wechat_component_appid,
            "component_appsecret": settings.wechat_component_appsecret,
            "component_verify_ticket": ticket,
        },
    )
    _redis.set(COMPONENT_TOKEN_KEY, data["component_access_token"], ex=data["expires_in"] - 300)
    return data["component_access_token"]


def _component_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    body = {"component_appid": get_settings().wechat_component_appid, **body}
    return _post(f"{_component_api()}/cgi-bin/component/{path}", body, component_access_token=_component_token())


def authorize_url(redirect_uri: str) -> str:
    """客户确认授权的页面地址。必须从开放平台登记的「授权发起页域名」下打开。"""
    pre_auth_code = _component_post("api_create_preauthcode", {})["pre_auth_code"]
    page = MOCK_PREFIX + "/cgi-bin/componentloginpage" if get_settings().wechat_mp_mock else LOGIN_PAGE
    # auth_type=1：只展示公众号
    return (
        f"{page}?component_appid={get_settings().wechat_component_appid}"
        f"&pre_auth_code={pre_auth_code}&redirect_uri={quote(redirect_uri, safe='')}&auth_type=1"
    )


def _cache_authorizer_token(appid: str, token: str, expires_in: int) -> None:
    _redis.set(f"wechat:authorizer_token:{appid}", token, ex=expires_in - 300)


def authorize(auth_code: str) -> tuple[dict[str, str], dict[str, str]]:
    """用回调里的 auth_code 换授权信息，返回 (凭证, 账号资料)。"""
    info = _component_post("api_query_auth", {"authorization_code": auth_code})["authorization_info"]
    appid = info["authorizer_appid"]
    _cache_authorizer_token(appid, info["authorizer_access_token"], info["expires_in"])

    detail = _component_post("api_get_authorizer_info", {"authorizer_appid": appid})["authorizer_info"]
    credentials = {"authorizer_appid": appid, "authorizer_refresh_token": info["authorizer_refresh_token"]}
    profile = {"external_id": appid, "nickname": detail.get("nick_name") or appid, "avatar_url": detail.get("head_img")}
    return credentials, profile


def mark_unauthorized(appid: str) -> None:
    _redis.delete(f"wechat:authorizer_token:{appid}")


def _authorizer_token(credentials: dict[str, str]) -> tuple[str, dict[str, str]]:
    appid = credentials["authorizer_appid"]
    if token := _redis.get(f"wechat:authorizer_token:{appid}"):
        return token, credentials
    try:
        data = _component_post(
            "api_authorizer_token",
            {"authorizer_appid": appid, "authorizer_refresh_token": credentials["authorizer_refresh_token"]},
        )
    except WechatError as exc:
        if exc.errcode in EXPIRED_CODES:
            raise LoginExpired("公众号授权已失效") from exc
        raise
    _cache_authorizer_token(appid, data["authorizer_access_token"], data["expires_in"])
    # refresh_token 可能会换新，调用方要写回数据库
    return data["authorizer_access_token"], {**credentials, "authorizer_refresh_token": data["authorizer_refresh_token"]}


# ---------- 草稿 / 发表 ----------


def _replace_images(content: str, token: str) -> str:
    """把正文里本平台的图片地址换成微信图床地址（外部图片会被微信过滤掉）。"""
    uploaded: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        key = match.group(1) + "/" + match.group(2)
        if key not in uploaded:
            path = article_image_path(match.group(1), match.group(2))
            uploaded[key] = _upload(f"{API}/cgi-bin/media/uploadimg", path, access_token=token)["url"]
        return f'src="{uploaded[key]}"'

    return ARTICLE_IMAGE_URL.sub(repl, content)


def _wait_published(token: str, publish_id: str, timeout: int = 180) -> dict[str, Any]:
    """发表是异步的，轮询结果（另有 PUBLISHJOBFINISH 事件推送，需要配置消息接收 URL）。"""
    deadline = time.monotonic() + timeout
    while True:
        data = _post(f"{API}/cgi-bin/freepublish/get", {"publish_id": publish_id}, access_token=token)
        status = data["publish_status"]
        if status == 0:
            items = data.get("article_detail", {}).get("item", [])
            return {"publish_id": publish_id, "article_id": data["article_id"], "url": items[0]["article_url"] if items else None}
        if status != 1:
            reasons = {2: "原创声明失败", 3: "发表失败", 4: "平台审核不通过", 5: "发表后已被删除", 6: "发表后已被封禁"}
            raise PublishError(f"公众号{reasons.get(status, f'发表失败（状态 {status}）')}")
        if time.monotonic() > deadline:
            # 还在发表中：已提交成功，结果去公众号后台的发表记录查看
            return {"publish_id": publish_id, "url": None, "pending": True}
        time.sleep(5)


def publish(
    credentials: dict[str, str], article: dict[str, Any], cover: Path, *, submit: bool
) -> tuple[dict[str, str], dict[str, Any]]:
    """存草稿；submit=True 时再发表（发表后对外可见）。返回 (刷新后的凭证, 结果)。"""
    try:
        token, credentials = _authorizer_token(credentials)
        try:
            return credentials, _publish(token, article, cover, submit)
        except WechatError as exc:
            if exc.errcode not in TOKEN_INVALID_CODES:
                raise
            mark_unauthorized(credentials["authorizer_appid"])
            token, credentials = _authorizer_token(credentials)
            return credentials, _publish(token, article, cover, submit)
    except WechatError as exc:
        raise PublishError(str(exc)) from exc


def _publish(token: str, article: dict[str, Any], cover: Path, submit: bool) -> dict[str, Any]:
    thumb = _upload(f"{API}/cgi-bin/material/add_material", cover, access_token=token, type="image")
    body = {**article, "content": _replace_images(article["content"], token), "thumb_media_id": thumb["media_id"]}
    media_id = _post(f"{API}/cgi-bin/draft/add", {"articles": [body]}, access_token=token)["media_id"]
    if not submit:
        return {"media_id": media_id, "draft": True}
    publish_id = _post(f"{API}/cgi-bin/freepublish/submit", {"media_id": media_id}, access_token=token)["publish_id"]
    return {"media_id": media_id, **_wait_published(token, publish_id)}
