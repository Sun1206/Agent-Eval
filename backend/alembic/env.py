"""
Alembic 环境配置 — 异步引擎 + 自动导入模型元数据
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 导入 Alembic 配置
config = context.config

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 导入所有模型，确保 Base.metadata 完整
from app.models import Base  # noqa: E402, F401
from app.config import get_settings  # noqa: E402

# 目标元数据
target_metadata = Base.metadata

# 其他配置
# exclude_tables 可用于排除第三方表


def get_sync_url() -> str:
    """获取同步数据库 URL（Alembic 迁移只能使用同步连接）"""
    settings = get_settings()
    return settings.postgres_sync_url


def run_migrations_offline() -> None:
    """
    离线迁移模式（生成 SQL 脚本，不连接数据库）
    用法: alembic upgrade head --sql > migration.sql
    """
    url = get_sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """在已有连接上执行迁移"""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    在线迁移模式（连接实际数据库执行）
    注意：虽然 env.py 使用异步引擎创建连接，但迁移操作本身是同步的。
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_sync_url()

    # 使用同步连接池创建可同步的引擎
    from sqlalchemy import create_engine

    connectable = create_engine(
        get_sync_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


def run_migrations_online() -> None:
    """在线迁移入口"""
    asyncio.run(run_async_migrations())


# Alembic 根据 offline/online 模式选择执行路径
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()