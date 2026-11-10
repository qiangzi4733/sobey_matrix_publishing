"""登录图形验证码：答案存 Redis，用一次就删，防止脚本反复试密码。

图片直接生成 SVG，不引入 Pillow 等绘图依赖。字符画成路径而不是 <text>，避免答案以纯文本出现在 SVG 里。
"""

import random
import secrets
import uuid

import redis

from app.config import get_settings

TTL_SECONDS = 5 * 60
# 去掉容易看混的 0/1，只用数字，和登录页设计稿一致
ALPHABET = "23456789"
LENGTH = 4
WIDTH, HEIGHT = 100, 36

_redis = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)

# 七段式数字笔画，坐标在 10x16 的格子里；段名 a~g 按惯例：a 上、b 右上、c 右下、d 下、e 左下、f 左上、g 中
_SEGMENTS = {
    "a": ((1, 1), (9, 1)),
    "b": ((9, 1), (9, 8)),
    "c": ((9, 8), (9, 15)),
    "d": ((1, 15), (9, 15)),
    "e": ((1, 8), (1, 15)),
    "f": ((1, 1), (1, 8)),
    "g": ((1, 8), (9, 8)),
}
_DIGITS = {
    "2": "abged",
    "3": "abgcd",
    "4": "fgbc",
    "5": "afgcd",
    "6": "afgedc",
    "7": "abc",
    "8": "abcdefg",
    "9": "abcdfg",
}


def _key(captcha_id: str) -> str:
    return f"captcha:{captcha_id}"


def _glyph(ch: str, x: float, rng: random.Random) -> str:
    # 每个笔画端点加一点抖动、整体随机倾斜，像手写一样
    parts = []
    for seg in _DIGITS[ch]:
        (x1, y1), (x2, y2) = _SEGMENTS[seg]
        j = lambda: rng.uniform(-0.8, 0.8)  # noqa: E731
        parts.append(f"M{x1 + j():.1f} {y1 + j():.1f}L{x2 + j():.1f} {y2 + j():.1f}")
    angle = rng.uniform(-18, 18)
    y = rng.uniform(6, 12)
    color = rng.choice(["#1d5c4a", "#1f3f8a", "#2d6a2e", "#5a2d82"])
    return (
        f'<path transform="translate({x:.1f} {y:.1f}) rotate({angle:.1f} 5 8) skewX({rng.uniform(-12, 12):.1f})" '
        f'd="{" ".join(parts)}" fill="none" stroke="{color}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def _render(code: str) -> str:
    rng = random.Random()
    noise = "".join(
        f'<path d="M{rng.uniform(0, WIDTH):.0f} {rng.uniform(0, HEIGHT):.0f}Q{rng.uniform(0, WIDTH):.0f} '
        f'{rng.uniform(0, HEIGHT):.0f} {rng.uniform(0, WIDTH):.0f} {rng.uniform(0, HEIGHT):.0f}" '
        f'fill="none" stroke="#9aa9c7" stroke-opacity="0.6" stroke-width="1"/>'
        for _ in range(4)
    )
    dots = "".join(
        f'<circle cx="{rng.uniform(0, WIDTH):.0f}" cy="{rng.uniform(0, HEIGHT):.0f}" r="0.9" fill="#8a9bbd"/>'
        for _ in range(24)
    )
    glyphs = "".join(_glyph(ch, 14 + i * 20 + rng.uniform(-2, 2), rng) for i, ch in enumerate(code))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">'
        f'<rect width="100%" height="100%" fill="#eef4f8"/>{noise}{dots}{glyphs}</svg>'
    )


def create() -> tuple[str, str]:
    """返回 (验证码 id, SVG 图片)。"""
    code = "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
    captcha_id = uuid.uuid4().hex
    _redis.set(_key(captcha_id), code, ex=TTL_SECONDS)
    return captcha_id, _render(code)


def verify(captcha_id: str, answer: str) -> bool:
    # 先取后删：不管对错都作废，输错要换一张，不能对同一张反复猜
    code = _redis.getdel(_key(captcha_id))
    return code is not None and secrets.compare_digest(code, answer.strip())
