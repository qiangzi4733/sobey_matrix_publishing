"""浏览器类平台共用的启动、截图工具。只在 browser-worker 里导入。"""

import logging
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from patchright.sync_api import Browser, BrowserContext, Page, Playwright

from app.config import get_settings

log = logging.getLogger(__name__)

StorageState = dict[str, Any]
# 平台要求短信验证码时调用：传入提示和验证弹窗截图，返回客户输入的验证码（超时为 None）
AskCode = Callable[[str, bytes | None], str | None]


def launch(p: Playwright) -> Browser:
    # 视频号上传要 Chrome 解码 H.264，Chromium 不行；抖音也统一用 Chrome
    return p.chromium.launch(channel="chrome", headless=get_settings().browser_headless)


def new_context(browser: Browser, state: StorageState | None = None) -> BrowserContext:
    return browser.new_context(
        storage_state=state,
        viewport={"width": 1440, "height": 900},
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )


def screenshot(page: Page, prefix: str) -> str | None:
    """保存失败现场截图，返回 debug_dir 下的文件名。"""
    debug_dir = Path(get_settings().debug_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}_{uuid.uuid4().hex[:8]}.png"
    try:
        page.screenshot(path=str(debug_dir / name), full_page=True)
        return name
    except Exception:
        log.exception("截图失败")
        return None
