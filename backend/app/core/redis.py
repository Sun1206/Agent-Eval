"""
Redis 异步连接管理 — 缓存 + 计数器

架构:
  RedisClient — 单例客户端，惰性初始化，封装常用操作
"""
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)

# 模块级单例
_client: Optional["RedisClient"] = None

# 默认过期时间
DEFAULT_TTL = 3600  # 秒


class RedisClient:
    """Redis 异步客户端封装"""

    def __init__(self):
        settings = get_settings()
        logger.info(f"初始化 Redis 连接: {settings.redis_host}:{settings.redis_port}")
        self._redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,  # 自动解码为 str，避免 bytes
            max_connections=50,     # 连接池大小，应对高并发
        )

    # ==================== 基础 KV 操作 ====================

    async def get(self, key: str) -> Optional[str]:
        """获取键值，不存在返回 None"""
        return await self._redis.get(key)

    async def set(self, key: str, value: str, ttl: int = DEFAULT_TTL) -> bool:
        """
        设置键值，带过期时间

        Args:
            key:   缓存键
            value: 缓存值（自动序列化为 JSON 字符串建议使用 json.dumps）
            ttl:   过期时间（秒），默认 3600
        """
        return await self._redis.set(key, value, ex=ttl)

    async def delete(self, key: str) -> int:
        """删除键，返回删除数量"""
        return await self._redis.delete(key)

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return await self._redis.exists(key) > 0

    # ==================== 计数器 ====================

    async def incr(self, key: str, amount: int = 1) -> int:
        """递增计数器，返回新值"""
        return await self._redis.incrby(key, amount)

    async def decr(self, key: str, amount: int = 1) -> int:
        """递减计数器，返回新值"""
        return await self._redis.decrby(key, amount)

    # ==================== 复杂操作 ====================

    async def get_json(self, key: str) -> Optional[dict]:
        """
        获取 JSON 缓存值

        数据以 JSON 字符串存储，读取时自动反序列化。
        """
        import json

        raw = await self.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: dict, ttl: int = DEFAULT_TTL) -> bool:
        """
        设置 JSON 缓存值

        数据自动序列化为 JSON 字符串存储。
        """
        import json

        return await self.set(key, json.dumps(value, ensure_ascii=False), ttl=ttl)

    # ==================== 生命周期 ====================

    async def close(self):
        """关闭连接"""
        if self._redis:
            await self._redis.aclose()
            logger.info("Redis 连接已关闭")

    async def is_alive(self) -> bool:
        """Ping 检查连接是否可用"""
        try:
            return await self._redis.ping()
        except Exception:
            return False


def get_redis() -> RedisClient:
    """获取 Redis 客户端单例（惰性初始化）"""
    global _client
    if _client is None:
        _client = RedisClient()
    return _client


async def close_redis():
    """关闭 Redis 客户端"""
    global _client
    if _client is not None:
        await _client.close()
        _client = None