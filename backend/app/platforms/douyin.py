"""抖音（创作者中心）：扫码登录、登录状态检测、视频发布（浏览器自动化）。

页面选择器和流程参考 social-auto-upload 的 uploader/douyin_uploader/main.py
（https://github.com/dreammis/social-auto-upload ，MIT License，Copyright (c) 2023 dreammis），
改为同步 API，登录状态以 storage_state 字典传入/传出，不落盘；短信验证码通过 ask_code 交给客户输入。

只在 browser-worker 容器里运行。
"""

import logging
import re
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from patchright.sync_api import Locator, Page, sync_playwright
from patchright.sync_api import TimeoutError as PWTimeout

from app.models import Platform
from app.platforms.base import LoginExpired, PublishError
from app.platforms.browser import AskCode, StorageState, launch, new_context, screenshot
from app.platforms.scheduling import validate_native_schedule

log = logging.getLogger(__name__)

HOME_URL = "https://creator.douyin.com/"
UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
USER_INFO_API = "https://creator.douyin.com/web/api/media/user/info/"
SCHEDULE_TZ = ZoneInfo("Asia/Shanghai")

# 2026-11 实测：登录页二维码在 #animate_qrcode_container 里（data:image）。
# 扫码后同一位置会换成扫码人的头像卡片（不是 data:image），所以要按 src 区分
QR_SELECTOR = 'div#animate_qrcode_container img[src^="data:image"], img[aria-label="二维码"][src^="data:image"]'
# 整个「扫码登录」栏（二维码 + 提示文字）
SCAN_AREA = "div#douyin_login_comp_scan_code"



def _visible(loc: Locator) -> bool:
    try:
        return loc.count() > 0 and loc.first.is_visible()
    except Exception:
        return False


def _on_login_page(page: Page) -> bool:
    return "creator-micro" not in page.url or _visible(page.locator(QR_SELECTOR)) or _visible(
        page.get_by_text("扫码登录", exact=True)
    )


# ---------- 短信 / 身份验证 ----------


# 2026-11 实测：扫码确认后弹出「身份验证」面板（字节通用验证组件），先列出验证方式，
# 选短信后同一面板换成「接收短信验证码」页（自动发送，有输入框和「验证」按钮）。
# 背后的手机号登录表单也有验证码输入框和「获取验证码」，所以一切操作都限定在面板内，
# 且面板内容会整体替换，每一步都要重新定位。
VERIFY_PANEL = '[class*="second_verify_panel"], [class*="uc_verification_component_layout"]'
SMS_OPTION = re.compile("短信")
CODE_INPUT = 'input[placeholder*="验证码"]:visible'


def _verify_dialog(page: Page) -> Locator | None:
    """身份验证面板（可能在 iframe 里）。没有返回 None。"""
    for frame in page.frames:
        panel = frame.locator(VERIFY_PANEL)
        if _visible(panel):
            return panel.first
    return None


def _handle_verification(page: Page, ask_code: AskCode | None) -> bool:
    """有身份验证面板就请客户输入短信验证码并提交。返回是否处理了面板。"""
    dialog = _verify_dialog(page)
    if dialog is None:
        return False
    if ask_code is None:
        raise PublishError("抖音要求身份验证，但当前流程无法让客户输入验证码", screenshot(page, "douyin_verify"))

    if not dialog.locator(CODE_INPUT).count():
        option = dialog.get_by_text(SMS_OPTION)
        if not _visible(option):
            # 只剩刷脸、扫码等其他验证方式，暂不支持
            raise PublishError("抖音要求的身份验证方式暂不支持", screenshot(page, "douyin_verify_unknown"))
        option.first.click()
        page.wait_for_timeout(2000)
        dialog = _verify_dialog(page)
        if dialog is None or not dialog.locator(CODE_INPUT).count():
            raise PublishError("选择短信验证后没有出现验证码输入框", screenshot(page, "douyin_verify_unknown"))

    # 一般选完短信就自动发送了；没发的话手动点一下
    send = dialog.get_by_text("获取验证码")
    if _visible(send):
        send.first.click()
        page.wait_for_timeout(1500)
    code = ask_code("抖音要求身份验证，请输入手机收到的短信验证码", dialog.screenshot())
    if not code:
        raise PublishError("等待短信验证码超时", screenshot(page, "douyin_verify_timeout"))

    code_input = dialog.locator(CODE_INPUT).first
    code_input.fill(code)
    page.wait_for_timeout(300)
    # 2026-11 实测：「验证」按钮不在面板元素内部（在旁边的底栏），按整页找。
    # 页面上文字恰好是「验证」的只有这个按钮（背后登录表单的按钮是「登录」）
    clicked = False
    for frame in page.frames:
        button = frame.get_by_role("button", name="验证", exact=True).or_(frame.get_by_text("验证", exact=True))
        if _visible(button):
            try:
                button.first.click(force=True, timeout=5000)
                clicked = True
                break
            except PWTimeout:
                continue
    if not clicked:
        code_input.press("Enter")
    page.wait_for_timeout(3000)
    still = _verify_dialog(page)
    if still is not None and still.locator(CODE_INPUT).count():
        raise PublishError("短信验证码不正确或已过期", screenshot(page, "douyin_verify_failed"))
    return True


# ---------- 扫码登录 ----------


def _read_profile(page: Page) -> dict[str, str]:
    resp = page.request.get(USER_INFO_API)
    try:
        user = resp.json()["user"]
    except Exception:
        log.warning("读取抖音账号信息失败：%s %s", resp.status, resp.text()[:300])
        return {}
    avatars = (user.get("avatar_thumb") or user.get("avatar_larger") or {}).get("url_list") or [""]
    # uid 不会变；抖音号（unique_id）客户可以改，不能拿来去重
    return {
        "external_id": str(user.get("uid") or ""),
        "nickname": user.get("nickname") or "",
        "avatar_url": avatars[0],
    }


def login(
    on_qr: Callable[[bytes], None],
    on_status: Callable[[str, str], None],
    ask_code: AskCode,
    timeout_seconds: int = 300,
) -> tuple[StorageState, dict[str, str]]:
    """打开创作者中心登录页，把二维码交给 on_qr，等客户用抖音 App 扫码确认。

    返回 (storage_state, profile)，profile 含 external_id / nickname / avatar_url。
    """
    with sync_playwright() as p:
        browser = launch(p)
        context = new_context(browser)
        try:
            page = context.new_page()
            page.goto(HOME_URL, wait_until="domcontentloaded")
            try:
                page.locator(QR_SELECTOR).first.wait_for(state="visible", timeout=30000)
            except PWTimeout:
                raise PublishError("没有找到抖音登录二维码", screenshot(page, "douyin_login")) from None

            last_png: bytes | None = None
            last_text = ""
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                if not _on_login_page(page) and _verify_dialog(page) is None:
                    break
                if _handle_verification(page, ask_code):
                    on_status("verifying", "验证已提交，正在登录")
                    continue
                # 推整个「扫码登录」栏而不只是二维码：扫码后这里会变成头像卡片等状态，客户要能看到
                area = page.locator(SCAN_AREA).first
                target = area if _visible(area) else page.locator(QR_SELECTOR).first
                if _visible(target):
                    png = target.screenshot()
                    if png != last_png:
                        on_qr(png)
                        last_png = png
                    # 按文字变化记录扫码栏状态，排查扫码后停住的情况（二维码动画不会触发）
                    text = " ".join(target.inner_text().split())
                    if text != last_text:
                        log.info("抖音扫码栏变化 %s：%s", page.url, text[:300])
                        last_text = text
                expired = page.get_by_text("二维码失效", exact=True)
                if _visible(expired):
                    expired.first.locator("..").click()
                page.wait_for_timeout(2000)
            else:
                raise TimeoutError("等待扫码超时")

            on_status("verifying", "登录成功，正在读取账号信息")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except PWTimeout:
                pass
            profile = _read_profile(page)
            if not profile.get("external_id"):
                raise PublishError("登录成功但未能读取抖音账号信息", screenshot(page, "douyin_profile"))
            state = context.storage_state()
            if not any(c["name"] == "sessionid" and c["value"] for c in state["cookies"]):
                raise PublishError("登录后没有拿到 sessionid", screenshot(page, "douyin_session"))
            return state, profile
        finally:
            context.close()
            browser.close()


# ---------- 登录状态检测 ----------


def check(state: StorageState) -> StorageState:
    with sync_playwright() as p:
        browser = launch(p)
        context = new_context(browser, state)
        try:
            page = context.new_page()
            page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=90000)
            # 登录失效时会被前端跳回登录页，等页面稳定再判断
            page.wait_for_timeout(3000)
            if _on_login_page(page):
                raise LoginExpired("抖音登录已失效")
            return context.storage_state()
        finally:
            context.close()
            browser.close()


# ---------- 发布视频 ----------


def _open_upload_page(page: Page) -> None:
    page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(3000)
    if _on_login_page(page):
        raise LoginExpired("抖音登录已失效")


def _upload_file(page: Page, video: Path, ask_code: AskCode | None) -> None:
    for _ in range(30):
        _handle_verification(page, ask_code)
        file_input = page.locator('input[type="file"]').first
        if file_input.count():
            file_input.set_input_files(str(video))
            break
        page.wait_for_timeout(1000)
    else:
        raise PublishError("未找到视频上传框", screenshot(page, "douyin_no_input"))
    # 选完文件会跳到发布表单页（两种版本的地址都出现过）
    try:
        page.wait_for_url(re.compile(r"/creator-micro/content/(publish|post/video)"), timeout=120000)
    except PWTimeout:
        raise PublishError("上传后没有进入发布页面", screenshot(page, "douyin_no_form")) from None


def _fill_form(page: Page, title: str, description: str, tags: list[str]) -> None:
    # 2026-06（上游）实测：标题 input，描述是 contenteditable 的 div.zone-container；
    # 新版表单要等视频上传一段时间才渲染，超时给足
    title_input = page.locator('input[placeholder*="填写作品标题"]').first
    title_input.wait_for(state="visible", timeout=120000)
    title_input.fill(title[:30])

    editor = page.locator('div.zone-container[contenteditable="true"]').first
    editor.wait_for(state="visible", timeout=120000)
    editor.click()
    page.keyboard.press("Control+KeyA")
    page.keyboard.press("Delete")
    if description.strip():
        page.keyboard.type(description.strip())
    for tag in tags:
        page.keyboard.type(" #" + tag)
        page.keyboard.press("Space")
    # 收起话题下拉，避免浮层挡住后面的点击
    page.keyboard.press("Escape")


def _wait_upload_complete(page: Page, video: Path, timeout_seconds: int = 3600) -> None:
    deadline = time.monotonic() + timeout_seconds
    retries = 0
    while time.monotonic() < deadline:
        if page.locator('[class^="long-card"] div:has-text("重新上传")').count():
            return
        if page.locator('div.progress-div > div:has-text("上传失败")').count():
            retries += 1
            if retries > 3:
                raise PublishError("视频上传连续失败 3 次", screenshot(page, "douyin_upload_failed"))
            log.warning("抖音上传失败，第 %s 次重试", retries)
            page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(str(video))
        page.wait_for_timeout(2000)
    raise PublishError("视频上传超时", screenshot(page, "douyin_upload_timeout"))


def _set_schedule(page: Page, when: datetime) -> None:
    expected = when.astimezone(SCHEDULE_TZ).strftime("%Y-%m-%d %H:%M")
    page.locator("[class^='radio']:has-text('定时发布')").click()
    page.wait_for_timeout(800)
    field = page.locator('.semi-input[placeholder="日期和时间"]')
    field.click()
    page.keyboard.press("Control+KeyA")
    page.keyboard.type(expected)
    page.keyboard.press("Enter")
    page.wait_for_timeout(800)
    # 超出「2 小时后～14 天内」时抖音会把输入改回默认值（当前时间 + 2 小时），回读核对
    actual = field.input_value()
    if actual != expected:
        raise PublishError(f"定时时间设置不正确：期望 {expected}，实际 {actual}", screenshot(page, "douyin_schedule"))
    # 点空白处收起日历浮层
    page.get_by_text("发布设置", exact=True).click()


def _set_covers(page: Page, portrait: Path | None, landscape: Path | None) -> None:
    """上传自定义封面。2026-11-03 实测：表单里「竖封面3:4」「横封面4:3」打开同一个弹窗，
    弹窗顶部切换「设置竖封面 / 设置横封面」，各自用「上传封面」；切到横封面时抖音会先把竖封面同步过去，
    再上传就覆盖掉。只设一张时另一张由抖音自动生成。"""
    if portrait is None and landscape is None:
        return
    page.evaluate(
        "() => document.querySelectorAll('.shepherd-element, .shepherd-modal-overlay-container').forEach(e => e.remove())"
    )
    page.locator('[class^="coverControl-"]').filter(has_text="竖封面3:4").locator('[class^="cover-"]').first.click()
    modal = page.locator("div.dy-creator-content-modal").first
    try:
        modal.wait_for(state="visible", timeout=15000)
    except PWTimeout:
        raise PublishError("封面设置弹窗没有打开", screenshot(page, "douyin_cover")) from None
    for tab, image in (("设置竖封面", portrait), ("设置横封面", landscape)):
        if image is None:
            continue
        modal.get_by_text(tab, exact=True).first.click()
        page.wait_for_timeout(1500)
        # 弹窗左侧「生成参考图」也有一个上传框，要用带「点击上传文件或拖拽」的那个
        modal.locator(
            ".semi-upload:has(.semi-upload-drag-area-main-text) input.semi-upload-hidden-input"
        ).first.set_input_files(str(image))
        page.wait_for_timeout(5000)
    modal.get_by_role("button", name="完成", exact=True).click()
    try:
        modal.wait_for(state="detached", timeout=15000)
    except PWTimeout:
        raise PublishError("封面没有设置成功", screenshot(page, "douyin_cover")) from None


def _ensure_cover(page: Page) -> None:
    """没有封面时抖音不让发布，选第一个推荐封面。"""
    if not _visible(page.get_by_text("请设置封面后再发布")):
        return
    cover = page.locator('[class^="recommendCover-"]').first
    if not cover.count():
        return
    cover.click()
    page.wait_for_timeout(1000)
    if _visible(page.get_by_text("是否确认应用此封面？")):
        page.get_by_role("button", name="确定").click()
        page.wait_for_timeout(1000)


def _submit(page: Page, ask_code: AskCode | None) -> None:
    for _ in range(60):
        # 新手引导、话题下拉会挡住发布按钮
        page.evaluate(
            "() => document.querySelectorAll('.shepherd-element, .shepherd-modal-overlay-container,"
            " [class*=\"mention-wrapper\"]').forEach(e => e.remove())"
        )
        _handle_verification(page, ask_code)
        button = page.get_by_role("button", name="发布", exact=True)
        if button.count():
            button.click(force=True)
        try:
            page.wait_for_url("**/creator-micro/content/manage**", timeout=5000)
            return
        except PWTimeout:
            _ensure_cover(page)
    raise PublishError("点击发布后没有进入作品管理页", screenshot(page, "douyin_submit"))


def publish(
    state: StorageState,
    video: Path,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    schedule_at: datetime | None = None,
    ask_code: AskCode | None = None,
    cover: Path | None = None,
    options: dict | None = None,
) -> StorageState:
    """发布一条视频，返回刷新后的 storage_state。schedule_at 不为空时使用抖音定时发布。
    cover 是竖封面，横封面在 options（见 video_options.DouyinOptions）。"""
    options = options or {}
    if schedule_at is not None:
        try:
            validate_native_schedule(Platform.douyin, schedule_at)
        except ValueError as exc:
            raise PublishError(str(exc)) from None
    with sync_playwright() as p:
        browser = launch(p)
        context = new_context(browser, state)
        page = context.new_page()
        try:
            _open_upload_page(page)
            _upload_file(page, video, ask_code)
            _fill_form(page, title, description, tags or [])
            _wait_upload_complete(page, video)
            _set_covers(page, cover, options.get("cover_landscape"))
            if schedule_at is not None:
                _set_schedule(page, schedule_at)
            _submit(page, ask_code)
            return context.storage_state()
        except (LoginExpired, PublishError):
            raise
        except Exception as exc:
            raise PublishError(f"发布失败：{exc}", screenshot(page, "douyin_error")) from exc
        finally:
            context.close()
            browser.close()
