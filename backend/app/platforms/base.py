class LoginExpired(Exception):
    """平台登录状态 / 授权已失效，需要客户重新扫码或授权。"""


class PublishError(Exception):
    def __init__(self, message: str, screenshot: str | None = None):
        super().__init__(message)
        # 失败现场截图的文件名（位于 debug_dir 下）
        self.screenshot = screenshot
