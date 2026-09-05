"""
安全工具类 — 密码哈希 + JWT + API Key

密码:   passlib argon2（主算法） + bcrypt（兼容旧密码）
JWT:    python-jose (HS256)
API Key: secrets.token_urlsafe + SHA256
"""
import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

# 密码哈希上下文
# argon2 为主算法（快速、抗 GPU、内存硬），bcrypt 为兼容算法（验证旧密码）
# deprecated="auto": 新密码用 argon2 哈希，旧 bcrypt 哈希仍可验证
# bcrypt__rounds=4: 旧密码验证时使用低轮数加速（Windows 纯 Python 环境下 12 轮需 21s）
_pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    bcrypt__rounds=4,
)

# Refresh Token 过期时间（天）
REFRESH_TOKEN_EXPIRE_DAYS = 7

# API Key 前缀
API_KEY_PREFIX = "agev_"


# ==================== 密码哈希 ====================

def hash_password(password: str) -> str:
    """对密码进行 bcrypt 哈希（同步，用于注册等低频场景）"""
    return _pwd_context.hash(password)


async def hash_password_async(password: str) -> str:
    """对密码进行 bcrypt 哈希（异步，避免阻塞事件循环）"""
    return await asyncio.to_thread(_pwd_context.hash, password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希是否匹配（同步）"""
    return _pwd_context.verify(plain_password, hashed_password)


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希是否匹配（异步，避免阻塞事件循环）"""
    return await asyncio.to_thread(_pwd_context.verify, plain_password, hashed_password)


# ==================== JWT ====================

def _create_token(user_id: UUID, token_type: str, expire_delta: timedelta) -> str:
    """创建 JWT Token（内部方法）"""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + expire_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: UUID) -> str:
    """创建 Access Token（过期时间从 config 读取）"""
    settings = get_settings()
    delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    return _create_token(user_id, "access", delta)


def create_refresh_token(user_id: UUID) -> str:
    """创建 Refresh Token（7 天过期）"""
    delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(user_id, "refresh", delta)


def decode_token(token: str) -> Optional[dict]:
    """
    解码并验证 JWT Token

    Returns:
        payload dict，验证失败返回 None
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None


# ==================== API Key ====================

def generate_api_key() -> tuple[str, str, str]:
    """
    生成 API Key

    Returns:
        (full_key, prefix, key_hash)
        full_key: 完整 Key（agev_ + 32 字符），仅返回一次
        prefix:   Key 前缀（前 10 字符），用于列表展示
        key_hash: SHA256 哈希，存入数据库
    """
    random_part = secrets.token_urlsafe(24)  # 24 bytes → 32 chars base64
    full_key = f"{API_KEY_PREFIX}{random_part}"
    prefix = full_key[:10]
    key_hash = _hash_api_key(full_key)
    return full_key, prefix, key_hash


def _hash_api_key(key: str) -> str:
    """对 API Key 进行 SHA256 哈希"""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def verify_api_key(plain_key: str, stored_hash: str) -> bool:
    """验证 API Key 是否匹配数据库中的哈希"""
    return _hash_api_key(plain_key) == stored_hash