"""
应用配置管理 - 从环境变量读取所有配置项

设计原则:
  - 所有配置项都从 .env 文件或环境变量读取，不硬编码
  - 使用 pydantic-settings 自动解析和校验配置
  - 通过 @lru_cache 实现单例模式，避免重复解析

配置文件位置: backend/.env（从 .env.example 复制修改）

读取优先级: 环境变量 > .env 文件 > 代码中的默认值
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    AgentScope 全局配置

    所有配置项都可以通过环境变量覆盖。
    例如: POSTGRES_HOST=localhost 等价于 Settings.postgres_host

    .env 文件自动加载，无需手动指定路径。
    """

    # pydantic-settings 配置
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],    # 配置文件路径（支持 backend/ 和项目根目录）
        env_file_encoding="utf-8",     # 文件编码
        case_sensitive=False,          # 环境变量不区分大小写
        extra="ignore",                # 忽略 .env 中多余的变量
    )

    # ==================== 应用基础配置 ====================
    app_name: str = "AgentScope"       # 应用名称
    app_env: str = "development"       # 运行环境: development / staging / production
    app_debug: bool = True             # 调试模式（开启后显示 Swagger 文档、允许所有跨域）
    app_secret_key: str = ""           # 应用密钥（必须在 .env 中配置，不可为空）

    # ==================== 服务器配置 ====================
    host: str = "0.0.0.0"             # 监听地址（0.0.0.0 表示所有网卡）
    port: int = 8000                   # 监听端口

    # ==================== CORS 跨域配置 ====================
    # 开发环境前端运行在 localhost:5173，后端运行在 localhost:8000
    # 需要配置 CORS 允许前端跨域访问后端 API
    cors_origins: list[str] = ["http://localhost:5173"]

    # ==================== PostgreSQL 配置 ====================
    # PostgreSQL 是主数据库，存储：用户、项目、Agent、数据集、评测结果、Bad Case 等
    # 通过 docker-compose 启动，默认端口 5432
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "agentscope"
    postgres_user: str = "root"
    postgres_password: str = ""         # 必须在 .env 中配置

    @property
    def postgres_url(self) -> str:
        """PostgreSQL 异步连接 URL（给 SQLAlchemy asyncpg 使用）"""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_sync_url(self) -> str:
        """PostgreSQL 同步连接 URL（给 Alembic 数据库迁移使用）"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ==================== ClickHouse 配置 ====================
    # ClickHouse 是 Trace 数据的存储引擎，适合海量时序数据的高效写入和查询
    # 通过 docker-compose 启动，默认 HTTP 端口 8123
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123        # HTTP 接口端口（8123），Native 端口是 9000
    clickhouse_user: str = "default"
    clickhouse_password: str = ""         # 必须在 .env 中配置
    clickhouse_db: str = "agentscope"

    # ==================== Redis 配置 ====================
    # Redis 用于缓存和计数器，目前主要预留，核心功能暂不依赖
    # 通过 docker-compose 启动，默认端口 6379
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""            # 开发环境默认无密码
    redis_db: int = 0                   # Redis 数据库编号（0-15）

    @property
    def redis_url(self) -> str:
        """Redis 连接 URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ==================== JWT 配置 ====================
    # JWT 用于 Web 端认证（登录后获取 access_token 和 refresh_token）
    jwt_secret_key: str = ""           # JWT 签名密钥（必须在 .env 中配置，不可为空）
    jwt_algorithm: str = "HS256"       # 签名算法
    jwt_access_token_expire_minutes: int = 1440  # Access Token 过期时间（分钟），默认 24 小时

    # ==================== API Key 配置 ====================
    # API Key 用于 SDK 认证，格式: agev_ + 32位随机字符串
    api_key_prefix: str = "agev_"

    # ==================== LLM 配置 ====================
    # LLM 用于评测评分（LLM-as-Judge），需要配置 API Key
    # 通义千问
    dashscope_api_key: Optional[str] = None

    # DeepSeek
    deepseek_api_key: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com"

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_default_model: str = "gpt-4o-mini"

    # ==================== 本地模型 ====================
    # BGE-M3 向量模型路径（用于语义相似度计算，目前预留）
    bge_m3_path: str = "D:/openclaw/models/bge-m3"

    # ==================== 向量数据库 ====================
    # ChromaDB 持久化目录（目前预留）
    chroma_persist_dir: str = str(Path(__file__).parent.parent / "data" / "chroma")

    # ==================== 项目路径 ====================
    @property
    def base_dir(self) -> Path:
        """项目根目录（backend/）"""
        return Path(__file__).parent.parent.resolve()

    @property
    def data_dir(self) -> Path:
        """数据目录（backend/data/），自动创建"""
        path = self.base_dir / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache()
def get_settings() -> Settings:
    """
    获取配置单例（带缓存）

    @lru_cache 确保整个应用生命周期内只创建一次 Settings 实例。
    多次调用返回同一个对象，避免重复解析 .env 文件。
    """
    s = Settings()

    # 启动时安全校验：关键密钥不可为空
    _check_required_secrets(s)

    return s


# 关键密钥校验白名单（开发环境跳过）
_REQUIRED_SECRETS = {
    "app_secret_key": "APP_SECRET_KEY",
    "jwt_secret_key": "JWT_SECRET_KEY",
    "postgres_password": "POSTGRES_PASSWORD",
}


def _check_required_secrets(s: Settings) -> None:
    """校验关键密钥是否已配置，未配置则警告"""
    import logging
    logger = logging.getLogger(__name__)

    missing = []
    for attr, env_name in _REQUIRED_SECRETS.items():
        value = getattr(s, attr, "")
        if not value:
            missing.append(env_name)

    if missing:
        logger.warning(
            f"以下关键配置项未在 .env 中设置: {', '.join(missing)}。"
            f"请在 .env 文件中配置这些值，生产环境不可为空。"
        )


# 快捷引用（其他模块可以直接 from app.config import settings）
settings = get_settings()
