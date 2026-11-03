"""扫码登录会话：浏览器 worker 写入二维码和进度，前端轮询读取。存在 Redis 里，过期自动清理。"""

import json
import uuid
from typing import Any

import redis

from app.config import get_settings

TTL_SECONDS = 15 * 60

_redis = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _key(login_id: str) -> str:
    return f"login_session:{login_id}"


def create(tenant_id: int, platform: str, relogin_account_id: int | None = None) -> str:
    login_id = uuid.uuid4().hex
    data = {
        "tenant_id": tenant_id,
        "platform": platform,
        "relogin_account_id": relogin_account_id,
        "status": "starting",
        "message": "正在打开登录页",
    }
    _redis.set(_key(login_id), json.dumps(data), ex=TTL_SECONDS)
    return login_id


def get(login_id: str) -> dict[str, Any] | None:
    raw = _redis.get(_key(login_id))
    return json.loads(raw) if raw else None


def update(login_id: str, **fields: Any) -> None:
    data = get(login_id)
    if data is None:
        return
    data.update(fields)
    _redis.set(_key(login_id), json.dumps(data), ex=TTL_SECONDS)
