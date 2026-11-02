import json
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet

from app.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return int(payload["sub"])


def _fernet() -> Fernet:
    key = get_settings().credentials_key
    if not key:
        raise RuntimeError("CREDENTIALS_KEY 未配置，无法加密平台凭证")
    return Fernet(key)


def encrypt_credentials(data: dict[str, Any]) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_credentials(token: str) -> dict[str, Any]:
    return json.loads(_fernet().decrypt(token.encode()))
