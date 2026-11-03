"""微信视频号：扫码登录、登录状态检测、视频发布（浏览器自动化）。

页面选择器和流程移植自 social-auto-upload 的 uploader/tencent_uploader/main.py
（https://github.com/dreammis/social-auto-upload ，MIT License，Copyright (c) 2023 dreammis），
改为同步 API，登录状态以 storage_state 字典传入/传出，不落盘。

只在 browser-worker 容器里运行（需要 patchright + Google Chrome）。
"""

import logging
import re
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from patchright.sync_api import Page, sync_playwright
from patchright.sync_api import TimeoutError as PWTimeout

from app.models import Platform
from app.platforms.base import LoginExpired, PublishError
from app.platforms.browser import AskCode, StorageState, launch, new_context, screenshot
from app.platforms.scheduling import validate_native_schedule

log = logging.getLogger(__name__)

LOGIN_URL = "https://channels.weixin.qq.com"
HOME_URL = "https://channels.weixin.qq.com/platform"
UPLOAD_URL = "https://channels.weixin.qq.com/platform/post/create"
QRCONNECT = "open.weixin.qq.com/connect/qrconnect"

# 视频号定时发表按北京时间选择
SCHEDULE_TZ = ZoneInfo("Asia/Shanghai")


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
    ask_code: AskCode | None = None,  # 视频号扫码登录没有短信验证，为与其他平台接口一致保留
    timeout_seconds: int = 300,
) -> tuple[StorageState, dict[str, str]]:
    """打开登录页，把二维码交给 on_qr，等待客户用微信扫码确认。

    返回 (storage_state, profile)，profile 含 external_id（视频号 ID）/ nickname / avatar_url。
    """
    with sync_playwright() as p:
        browser = launch(p)
        context = new_context(browser)
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
                shot = screenshot(page, "channels_profile")
                raise PublishError("登录成功但未能读取视频号 ID", shot)
            return context.storage_state(), {
                "external_id": profile["uniq_id"],
                "nickname": profile.get("nickname", ""),
                "avatar_url": profile.get("avatar_url", ""),
            }
        finally:
            context.close()
            browser.close()


# ---------- 登录状态检测 ----------


def check(state: StorageState) -> StorageState:
    """打开首页验证登录状态。有效则返回刷新后的 storage_state，失效抛 LoginExpired。"""
    with sync_playwright() as p:
        browser = launch(p)
        context = new_context(browser, state)
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
    raise PublishError("未找到视频上传框", screenshot(page, "channels_no_input"))


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
        raise PublishError("视频号要求管理员微信扫码实名验证，请在视频号助手完成后重试", screenshot(page, "channels_verify"))


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
                    raise PublishError(f"视频上传连续失败 {max_retries} 次", screenshot(page, "channels_upload_failed"))
                log.warning("视频号上传出错，第 %s 次重试", retries)
                delete.click()
                page.get_by_role("button", name="删除", exact=True).click()
                _upload_file(page, video)
        except PublishError:
            raise
        except Exception:
            pass
        page.wait_for_timeout(2000)
    raise PublishError("视频上传超时", screenshot(page, "channels_upload_timeout"))


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


def _set_cover(page: Page, cover: Path) -> None:
    """上传竖封面（3:4「个人主页卡片」）。选择器参照上游 tencent_uploader（2026-10），本项目尚未实测。"""
    page.locator("div.vertical-cover-wrap").first.click(timeout=10000)
    dialog = page.locator("div.weui-desktop-dialog:visible").filter(has_text=re.compile("编辑个人主页卡片|编辑封面")).first
    try:
        dialog.wait_for(state="visible", timeout=10000)
    except PWTimeout:
        raise PublishError("封面设置弹窗没有打开", screenshot(page, "channels_cover")) from None
    dialog.locator('.single-cover-uploader-wrap input[type="file"]').first.set_input_files(str(cover))
    page.wait_for_timeout(2000)
    # 图片比例不是 3:4 时会先弹裁剪框
    crop = page.locator("div.weui-desktop-dialog:visible").filter(has_text="裁剪封面图").first
    if crop.count():
        crop.locator('div.weui-desktop-dialog__ft button:has-text("确定")').first.click()
        page.wait_for_timeout(1000)
    dialog.locator('div.weui-desktop-dialog__ft button.weui-desktop-btn_primary:has-text("确认")').first.click()
    try:
        dialog.wait_for(state="hidden", timeout=15000)
    except PWTimeout:
        raise PublishError("封面没有设置成功", screenshot(page, "channels_cover")) from None


def _set_schedule(page: Page, when: datetime) -> None:
    """使用视频号自带的「定时发表」，到点由平台发布。"""
    local = when.astimezone(SCHEDULE_TZ)
    expected = local.strftime("%Y-%m-%d %H:%M")

    section = page.locator("div.form-item").filter(has=page.locator("div.label", has_text="定时发表"))
    section.locator("label").filter(has_text=re.compile(r"^\s*定时\s*$")).click()
    date_input = page.locator('input[placeholder="请选择发表时间"]')
    date_input.click()

    # 翻到目标月份。日历可能停在上次选过的月份，前后都要能翻
    labels = page.locator("span.weui-desktop-picker__panel__label")
    for _ in range(3):
        year, month = (int(re.sub(r"\D", "", t)) for t in labels.all_inner_texts()[:2])
        diff = (local.year - year) * 12 + (local.month - month)
        if diff == 0:
            break
        arrow = "right" if diff > 0 else "left"
        page.locator(f"button.weui-desktop-btn__icon__{arrow}:visible").first.click(timeout=5000)
        page.wait_for_timeout(300)
    else:
        raise PublishError(f"定时发表日历翻不到 {local:%Y年%m月}", screenshot(page, "channels_schedule"))

    days = page.locator("table.weui-desktop-picker__table a:not(.weui-desktop-picker__faded)")
    day = days.filter(has_text=re.compile(rf"^\s*{local.day}\s*$")).first
    if not day.count() or "weui-desktop-picker__disabled" in (day.get_attribute("class") or ""):
        raise PublishError(f"视频号不允许定时到 {local:%m月%d日}", screenshot(page, "channels_schedule"))
    day.click()

    page.locator('input[placeholder="请选择时间"]').click()
    page.locator("ol.weui-desktop-picker__time__hour li").filter(has_text=re.compile(rf"^{local:%H}$")).click()
    page.locator("ol.weui-desktop-picker__time__minute li").filter(has_text=re.compile(rf"^{local:%M}$")).click()
    page.wait_for_timeout(500)

    actual = date_input.input_value()
    if actual != expected:
        raise PublishError(f"定时时间设置不正确：期望 {expected}，实际 {actual}", screenshot(page, "channels_schedule"))
    # 点表单项标题收起日历浮层，免得挡住后面的按钮
    section.locator("div.label").click()
    page.wait_for_timeout(300)
    if date_input.input_value() != expected:
        raise PublishError("收起日历后定时时间被重置", screenshot(page, "channels_schedule"))


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
    raise PublishError("点击发表后页面没有变化", screenshot(page, "channels_submit"))


def publish(
    state: StorageState,
    video: Path,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    schedule_at: datetime | None = None,
    ask_code: AskCode | None = None,  # 视频号目前没有短信验证环节，为与其他平台接口一致保留
    cover: Path | None = None,
    options: dict | None = None,  # 视频号暂无专属配置，见 video_options.ChannelsOptions
) -> StorageState:
    """发布一条视频，返回刷新后的 storage_state。schedule_at 不为空时使用视频号定时发表。"""
    if schedule_at is not None:
        try:
            validate_native_schedule(Platform.channels, schedule_at)
        except ValueError as exc:
            raise PublishError(str(exc)) from None
    with sync_playwright() as p:
        browser = launch(p)
        context = new_context(browser, state)
        page = context.new_page()
        try:
            _open_upload_page(page)
            _upload_file(page, video)
            _check_realtime_verification(page)
            _fill_description(page, title, tags or [], description)
            _wait_upload_complete(page, video)
            if cover is not None:
                _set_cover(page, cover)
            if schedule_at is not None:
                _set_schedule(page, schedule_at)
            _set_short_title(page, title)
            _submit(page)
            return context.storage_state()
        except (LoginExpired, PublishError):
            raise
        except Exception as exc:
            raise PublishError(f"发布失败：{exc}", screenshot(page, "channels_error")) from exc
        finally:
            context.close()
            browser.close()
