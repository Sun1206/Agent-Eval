"""
认证依赖注入 — JWT 认证 + API Key 认证

性能优化要点:
  - API Key 认证：先计算哈希，再用哈希精确查询（利用索引），避免循环比对
  - API Key 认证：去掉每次请求的 last_used_at 写入，改为惰性更新
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token, verify_api_key, _hash_api_key
from app.models.user import ApiKey, User


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    从 JWT Bearer Token 解析当前用户

    Header: Authorization: Bearer <access_token>
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="认证格式错误，应为 Bearer <token>")

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="请使用 Access Token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token 内容无效")

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="用户已被禁用")

    return user


async def get_current_user_from_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    从 API Key 解析当前用户

    Header: X-API-Key: agev_xxxxxxxx...

    性能优化:
      - 先计算 SHA256 哈希，再用哈希精确查询（利用 idx_api_keys_hash 索引）
      - 去掉每次请求的 last_used_at 实时写入，改为惰性批量更新
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="未提供 API Key")

    # 先计算哈希，再用哈希精确查询（利用索引，O(1) 查找）
    key_hash = _hash_api_key(x_api_key)
    result = await db.execute(
        select(ApiKey, User)
        .join(User, ApiKey.user_id == User.id)
        .where(
            ApiKey.is_active == True,
            ApiKey.key_hash == key_hash,
        )
    )
    row = result.one_or_none()

    if row is None:
        raise HTTPException(status_code=401, detail="API Key 无效")

    matched_key, user = row

    # 检查过期
    if matched_key.expires_at:
        if matched_key.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="API Key 已过期")

    # 惰性更新 last_used_at：距上次更新超过 5 分钟才写库，减少高频写入
    now = datetime.now(timezone.utc)
    if matched_key.last_used_at is None or (now - matched_key.last_used_at).total_seconds() > 300:
        await db.execute(
            update(ApiKey)
            .where(ApiKey.id == matched_key.id)
            .values(last_used_at=now)
        )
        await db.commit()

    if not user.is_active:
        raise HTTPException(status_code=401, detail="用户已被禁用")

    return user
