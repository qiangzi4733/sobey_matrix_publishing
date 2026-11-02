from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://matrix:matrix@db:5432/matrix"
    redis_url: str = "redis://redis:6379/0"

    # 签发登录 JWT 用
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 60 * 24 * 7

    # 加密存储平台凭证（token、cookie）用的 Fernet key，生产环境必须单独设置
    credentials_key: str = ""

    # 微信开放平台第三方平台
    wechat_component_appid: str = ""
    wechat_component_appsecret: str = ""
    wechat_component_token: str = ""
    wechat_component_aes_key: str = ""

    # 对外访问地址，用于拼接授权回调
    public_base_url: str = "http://127.0.0.1:5173"

    # 上传的视频、失败截图；backend 与 browser-worker 共享同一个卷
    media_dir: str = "/data/media"
    debug_dir: str = "/data/debug"

    # 浏览器自动化：生产环境保持 headless
    browser_headless: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
