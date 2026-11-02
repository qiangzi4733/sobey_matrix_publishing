"""平台中途要求短信验证码时，在浏览器 worker 和客户之间传递验证码（存在 Redis）。

scope 用来区分场景：扫码登录是 login:{login_id}，发布任务是 task:{task_id}。
worker 调 request() 把验证弹窗截图和提示推给前端，再 wait_for_code() 等客户提交。
"""

import base64
import json
import time

import redis

from app.config import get_settings

TTL_SECONDS = 10 * 60

_redis = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _key(scope: str) -> str:
    return f"verify:{scope}"


def _code_key(scope: str) -> str:
    return f"verify_code:{scope}"


def request(scope: str, message: str, image_png: bytes | None = None) -> None:
    data = {"message": message, "image": None}
    if image_png:
        data["image"] = "data:image/png;base64," + base64.b64encode(image_png).decode()
    _redis.delete(_code_key(scope))
    _redis.set(_key(scope), json.dumps(data), ex=TTL_SECONDS)


def pending(scope: str) -> dict | None:
    raw = _redis.get(_key(scope))
    return json.loads(raw) if raw else None


def submit(scope: str, code: str) -> bool:
    if pending(scope) is None:
        return False
    _redis.set(_code_key(scope), code, ex=TTL_SECONDS)
    return True


def wait_for_code(scope: str, timeout_seconds: int = 300) -> str | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if code := _redis.getdel(_code_key(scope)):
            _redis.delete(_key(scope))
            return code
        time.sleep(2)
    _redis.delete(_key(scope))
    return None


def asker(scope: str, on_waiting=None):
    """生成交给平台模块的 ask_code(message, image_png) -> str | None 回调。"""

    def ask_code(message: str, image_png: bytes | None) -> str | None:
        request(scope, message, image_png)
        if on_waiting:
            on_waiting(message)
        return wait_for_code(scope)

    return ask_code
