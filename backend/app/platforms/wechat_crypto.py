"""开放平台推送消息的签名和加解密（官方 WXBizMsgCrypt 方案：AES-256-CBC，PKCS#7 按 32 字节补位）。

推送正文：16 字节随机串 + 4 字节网络序消息长度 + 消息 XML + 第三方平台 AppID。"""

import base64
import hashlib
import hmac
import os
import struct
import xml.etree.ElementTree as ET

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.config import get_settings

BLOCK = 32


class CryptoError(Exception):
    pass


def _cipher() -> Cipher:
    key = base64.b64decode(get_settings().wechat_component_aes_key + "=")
    return Cipher(algorithms.AES(key), modes.CBC(key[:16]))


def signature(timestamp: str, nonce: str, encrypt: str) -> str:
    parts = sorted([get_settings().wechat_component_token, timestamp, nonce, encrypt])
    return hashlib.sha1("".join(parts).encode()).hexdigest()


def encrypt(xml: str) -> str:
    body = xml.encode()
    raw = os.urandom(16) + struct.pack(">I", len(body)) + body + get_settings().wechat_component_appid.encode()
    pad = BLOCK - len(raw) % BLOCK
    raw += bytes([pad]) * pad
    encryptor = _cipher().encryptor()
    return base64.b64encode(encryptor.update(raw) + encryptor.finalize()).decode()


def decrypt(encrypted: str) -> str:
    decryptor = _cipher().decryptor()
    raw = decryptor.update(base64.b64decode(encrypted)) + decryptor.finalize()
    pad = raw[-1]
    if not 1 <= pad <= BLOCK:
        raise CryptoError("补位不正确")
    content = raw[16:-pad]
    (length,) = struct.unpack(">I", content[:4])
    xml, appid = content[4 : 4 + length], content[4 + length :]
    if appid.decode() != get_settings().wechat_component_appid:
        raise CryptoError("AppID 不匹配")
    return xml.decode()


def parse_push(body: bytes, timestamp: str, nonce: str, msg_signature: str) -> dict[str, str]:
    """校验签名并解密推送，返回解密后 XML 的一级字段。"""
    encrypted = ET.fromstring(body).findtext("Encrypt") or ""
    if not hmac.compare_digest(signature(timestamp, nonce, encrypted), msg_signature):
        raise CryptoError("签名不正确")
    return {child.tag: child.text or "" for child in ET.fromstring(decrypt(encrypted))}
