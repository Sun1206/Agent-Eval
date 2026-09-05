"""
PostgreSQL 异步连接管理

架构:
  _async_engine      — 模块级单例，惰性初始化
  async_session_factory — 模块级单例，惰性初始化
  get_db()           — FastAPI Depends 依赖注入（async generator）

连接池配置:
  pool_size=20       — 常驻连接数
  max_overflow=10    — 最大溢出连接（峰值 30）
  pool_pre_ping=True — 每次使用前 ping，规避断连接
"""
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

# 模块级单例（None 表示未初始化）
_async_engine = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    """获取或创建异步引擎（惰性初始化）"""
    global _async_engine
    if _async_engine is None:
        settings = get_settings()
        logger.info(
            f"初始化 PostgreSQL 连接池: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        )
        _async_engine = create_async_engine(
            settings.postgres_url,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,        # 开启 pre_ping，规避断连接（开销极小，约0.1ms）
            pool_recycle=3600,         # 每小时回收连接，避免 PG 端超时断开
            echo=False,                # 关闭 SQL 日志，避免大量 IO 影响性能
        )
    return _async_engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取或创建 session 工厂（惰性初始化）"""
    global async_session_factory
    if async_session_factory is None:
        engine = get_engine()
        async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,  # 提交后不使对象过期，避免延迟加载异常
        )
    return async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入: 每个请求一个数据库 session

    用法:
        @router.get("/users")
        async def list_users(db: AsyncSession = Depends(get_db)):
            ...
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()  # 无异常则提交
    except Exception:
        await session.rollback()  # 有异常则回滚
        raise
    finally:
        await session.close()  # 归还连接到池


async def close_engine():
    """关闭引擎，释放连接池（应用关闭时调用）"""
    global _async_engine, async_session_factory
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        async_session_factory = None
        logger.info("PostgreSQL 连接池已关闭")