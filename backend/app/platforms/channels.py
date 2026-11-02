"""微信视频号：扫码登录、登录状态检测、视频发布（浏览器自动化）。

页面选择器和流程移植自 social-auto-upload 的 uploader/tencent_uploader/main.py
（https://github.com/dreammis/social-auto-upload ，MIT License，Copyright (c) 2023 dreammis），
改为同步 API，登录状态以 storage_state 字典传入/传出，不落盘。

只在 browser-worker 容器里运行（需要 patchright + Google Chrome）。
"""

import logging
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from patchright.sync_api import Browser, Page, Playwright, sync_playwright
from patchright.sync_api import TimeoutError as PWTimeout

from app.config import get_settings
from app.platforms.base import LoginExpired, PublishError

log = logging.getLogger(__name__)

LOGIN_URL = "https://channels.weixin.qq.com"
HOME_URL = "https://channels.weixin.qq.com/platform"
UPLOAD_URL = "https://channels.weixin.qq.com/platform/post/create"
QRCONNECT = "open.weixin.qq.com/connect/qrconnect"

StorageState = dict[str, Any]


def _launch(p: Playwright) -> Browser:
    # 视频号上传要 Chrome 解码 H.264，Chromium 不行
    return p.chromium.launch(channel="chrome", headless=get_settings().browser_headless)


def _new_context(browser: Browser, state: StorageState | None = None):
    return browser.new_context(
        storage_state=state,
        viewport={"width": 1440, "height": 900},
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )


def _screenshot(page: Page, prefix: str) -> str | None:
    debug_dir = Path(get_settings().debug_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}_{uuid.uuid4().hex[:8]}.png"
    try:
        page.screenshot(path=str(debug_dir / name), full_page=True)
        return name
    except Exception:
        log.exception("截图失败")
        return None


def _redirected_to_login(page: Page, wait_ms: int = 8000) -> bool:
    # 登录失效时页面先停在目标页，随后由前端 JS 跳到登录页，必须等跳转完成再判断
    try:
        page.wait_for_url("**/login.html**", timeout=wait_ms)
        return True
    except PWTimeout:
        pass
    return any(QRCONNECT in fr.url for fr in page.frames)


# ---------- 扫码登录 ----------


def _qr_png(page: Page) -> bytes | None:
    """截取登录二维码图片。

    2026-11 实测：二维码在 open.weixin.qq.com/connect/qrconnect 的 iframe 里，可见的是
    img.web_qrcode_img；同一 iframe 里还有隐藏的 img.qrcode，所以必须按可见过滤。
    """
    for frame in page.frames:
        img = frame.locator("img.web_qrcode_img:visible, img.qrcode:visible").first
        try:
            if img.count():
                return img.screenshot()
        except Exception:
            continue
    return None


def _page_text_contains(page: Page, *texts: str) -> bool:
    for frame in page.frames:
        for text in texts:
            try:
                loc = frame.get_by_text(text).first
                if loc.count() and loc.is_visible():
                    return True
            except Exception:
                continue
    return False


def _login_completed(page: Page) -> bool:
    url = page.url
    return "/platform" in url and "login" not in url and not any(QRCONNECT in fr.url for fr in page.frames)


def _read_profile_from_page(page: Page) -> dict[str, str]:
    """auth_data 接口没抓到时，从首页 DOM 兜底读取昵称和视频号 ID。"""
    profile: dict[str, str] = {}
    for key, selector in (("nickname", ".finder-nickname"), ("uniq_id", ".finder-uniq-id")):
        loc = page.locator(selector).first
        try:
            if loc.count():
                profile[key] = loc.inner_text().strip()
        except Exception:
            continue
    if uniq := profile.get("uniq_id"):
        profile["uniq_id"] = uniq.replace("视频号ID", "").strip(": ：")
    return profile


def login(
    on_qr: Callable[[bytes], None],
    on_status: Callable[[str, str], None],
    timeout_seconds: int = 300,
) -> tuple[StorageState, dict[str, str]]:
    """打开登录页，把二维码交给 on_qr，等待客户用微信扫码确认。

    返回 (storage_state, profile)。profile 含 nickname / uniq_id / avatar_url（尽量获取）。
    """
    with sync_playwright() as p:
        browser = _launch(p)
        context = _new_context(browser)
        profile: dict[str, str] = {}

        def capture_profile(response) -> None:
            if "auth/auth_data" not in response.url:
                return
            try:
                user = response.json()["data"]["finderUser"]
            except Exception:
                return
            profile.update(
                nickname=user.get("nickname", ""),
                uniq_id=user.get("uniqId", ""),
                avatar_url=user.get("headImgUrl", ""),
            )

        context.on("response", capture_profile)
        try:
            page = context.new_page()
            page.goto(LOGIN_URL, wait_until="domcontentloaded")

            last_qr: bytes | None = None
            scanned = False
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                if _login_completed(page):
                    break
                qr = _qr_png(page)
                # 二维码会自己刷新，变化了就推给前端
                if qr and qr != last_qr:
                    on_qr(qr)
                    last_qr = qr
                if not scanned and _page_text_contains(page, "已扫码", "扫描成功", "需在手机上进行确认"):
                    scanned = True
                    on_status("scanned", "已扫码，请在手机上确认登录")
                if _page_text_contains(page, "二维码已过期", "二维码已失效"):
                    page.reload(wait_until="domcontentloaded")
                    scanned = False
                page.wait_for_timeout(2000)
            else:
                raise TimeoutError("等待扫码超时")

            on_status("verifying", "登录成功，正在读取账号信息")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except PWTimeout:
                pass
            if not profile.get("uniq_id"):
                profile.update({k: v for k, v in _read_profile_from_page(page).items() if v})
            if not profile.get("uniq_id"):
                shot = _screenshot(page, "channels_profile")
                raise PublishError("登录成功但未能读取视频号 ID", shot)
            return context.storage_state(), profile
        finally:
            context.close()
            browser.close()


# ---------- 登录状态检测 ----------


def check(state: StorageState) -> StorageState:
    """打开首页验证登录状态。有效则返回刷新后的 storage_state，失效抛 LoginExpired。"""
    with sync_playwright() as p:
        browser = _launch(p)
        context = _new_context(browser, state)
        try:
            page = context.new_page()
            page.goto(HOME_URL, wait_until="domcontentloaded")
            if _redirected_to_login(page):
                raise LoginExpired("视频号登录已失效")
            return context.storage_state()
        finally:
            context.close()
            browser.close()


# ---------- 发布视频 ----------


def _format_short_title(title: str) -> str:
    """短标题要求 6~16 字，只允许部分符号；按 7~15 字从严处理。"""
    allowed = "《》“”:+?%°"
    chars = [c if c.isalnum() or c in allowed else " " if c == "," else "" for c in title]
    value = "".join(chars).strip()[:15]
    if len(value) < 7:
        value = (value + "，精彩内容分享")[:7] if value else "精彩视频内容分享"
    return value


def _open_upload_page(page: Page) -> None:
    # 直接打开 /post/create 会被跳回首页且表单不挂载，要从首页点「发表视频」进入
    page.goto(HOME_URL, timeout=120000, wait_until="domcontentloaded")
    if _redirected_to_login(page):
        raise LoginExpired("视频号登录已失效")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PWTimeout:
        pass
    entry = page.locator("button.weui-desktop-btn", has_text="发表视频").first
    try:
        entry.wait_for(state="visible", timeout=30000)
        entry.click()
    except PWTimeout:
        page.goto(UPLOAD_URL, timeout=120000, wait_until="domcontentloaded")
    try:
        page.wait_for_url("**/platform/post/create", timeout=60000)
        page.wait_for_load_state("networkidle", timeout=30000)
    except PWTimeout:
        pass


def _find_file_input(page: Page):
    for frame in page.frames:
        try:
            fi = frame.locator('input[type="file"]')
            if fi.count():
                return fi.first
        except Exception:
            continue
    return None


def _upload_file(page: Page, video: Path) -> None:
    for _ in range(60):
        if fi := _find_file_input(page):
            fi.set_input_files(str(video))
            return
        page.wait_for_timeout(1000)
    raise PublishError("未找到视频上传框", _screenshot(page, "channels_no_input"))


def _dismiss_dialogs(page: Page) -> None:
    # 上传后偶发「切换视频号」弹窗遮挡表单，点取消继续用当前账号
    for selector in (
        '.changeAccount-dialog button:has-text("取消")',
        ".changeAccount-dialog .weui-desktop-dialog__close-btn",
    ):
        btn = page.locator(selector).first
        try:
            if btn.count() and btn.is_visible():
                btn.click(timeout=2000)
                page.wait_for_timeout(600)
                return
        except Exception:
            continue


def _check_realtime_verification(page: Page) -> None:
    dialog = page.locator("div.weui-desktop-dialog__wrp:visible").filter(has_text="实名验证").first
    if dialog.count() and dialog.is_visible():
        raise PublishError("视频号要求管理员微信扫码实名验证，请在视频号助手完成后重试", _screenshot(page, "channels_verify"))


def _fill_description(page: Page, title: str, tags: list[str], description: str) -> None:
    editor = page.locator("div.input-editor")
    for _ in range(4):
        try:
            editor.click(timeout=5000)
            break
        except Exception:
            _dismiss_dialogs(page)
            page.wait_for_timeout(500)
    else:
        editor.click(timeout=8000)
    page.keyboard.type(title)
    page.keyboard.press("Enter")
    for tag in tags:
        page.keyboard.type("#" + tag)
        page.keyboard.press("Space")
    if description:
        page.keyboard.press("Enter")
        page.keyboard.type(description)


def _wait_upload_complete(page: Page, video: Path, timeout_seconds: int = 3600, max_retries: int = 3) -> None:
    deadline = time.monotonic() + timeout_seconds
    retries = 0
    while time.monotonic() < deadline:
        btn = page.locator('div.form-btns button:has-text("发表"):visible').first
        try:
            if btn.count() and not btn.is_disabled() and "weui-desktop-btn_disabled" not in (btn.get_attribute("class") or ""):
                return
            failed = page.locator("div.status-msg.error").count()
            delete = page.locator('div.media-status-content div.tag-inner:has-text("删除")')
            if failed and delete.count():
                retries += 1
                if retries > max_retries:
                    raise PublishError(f"视频上传连续失败 {max_retries} 次", _screenshot(page, "channels_upload_failed"))
                log.warning("视频号上传出错，第 %s 次重试", retries)
                delete.click()
                page.get_by_role("button", name="删除", exact=True).click()
                _upload_file(page, video)
        except PublishError:
            raise
        except Exception:
            pass
        page.wait_for_timeout(2000)
    raise PublishError("视频上传超时", _screenshot(page, "channels_upload_timeout"))


def _set_short_title(page: Page, title: str) -> None:
    field = page.locator('input[placeholder="填写短标题有机会获得更多流量"]').first
    if not field.count():
        field = (
            page.get_by_text("短标题", exact=True)
            .locator("..")
            .locator("xpath=following-sibling::div")
            .locator('span input[type="text"]')
        )
    if field.count():
        field.fill(_format_short_title(title))


def _submit(page: Page) -> None:
    btn = page.get_by_role("button", name="发表", exact=True).first
    for _ in range(60):
        _dismiss_dialogs(page)
        if btn.count() and btn.is_visible():
            break
        page.wait_for_timeout(1000)
    for _ in range(20):
        try:
            btn.click(timeout=4000)
        except Exception:
            try:
                btn.evaluate("el => el.click()")
            except Exception:
                pass
        # 发表成功后会离开 /post/create，或者发表按钮消失
        for _ in range(10):
            page.wait_for_timeout(1000)
            if "/post/create" not in page.url or not btn.count():
                return
    raise PublishError("点击发表后页面没有变化", _screenshot(page, "channels_submit"))


def publish(
    state: StorageState,
    video: Path,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
) -> StorageState:
    """发布一条视频，返回刷新后的 storage_state。"""
    with sync_playwright() as p:
        browser = _launch(p)
        context = _new_context(browser, state)
        page = context.new_page()
        try:
            _open_upload_page(page)
            _upload_file(page, video)
            _check_realtime_verification(page)
            _fill_description(page, title, tags or [], description)
            _wait_upload_complete(page, video)
            _set_short_title(page, title)
            _submit(page)
            return context.storage_state()
        except (LoginExpired, PublishError):
            raise
        except Exception as exc:
            raise PublishError(f"发布失败：{exc}", _screenshot(page, "channels_error")) from exc
        finally:
            context.close()
            browser.close()
