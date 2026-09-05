"""
AgentScope FastAPI 应用入口

这是整个后端服务的启动文件，职责：
  1. 创建 FastAPI 应用实例
  2. 注册中间件（CORS 跨域、请求日志）
  3. 注册全局异常处理器（统一错误响应格式）
  4. 注册所有 API 路由模块
  5. 管理应用生命周期（启动/关闭时的连接池管理）

启动命令: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

# 配置日志格式：时间 [级别] 模块名 - 消息
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ==================== 评测任务恢复 ====================

async def _recover_stale_eval_runs():
    """
    服务启动时，将 PENDING/RUNNING 状态的评测任务标记为 FAILED。

    服务中断后，后台任务不会自动恢复，这些任务会永远卡在 PENDING/RUNNING 状态。
    将它们标记为 FAILED，用户可以手动重试。
    """
    try:
        from app.core.database import get_session_factory
        from app.models.evaluation import EvalRun
        from sqlalchemy import update

        factory = get_session_factory()
        async with factory() as db:
            result = await db.execute(
                update(EvalRun)
                .where(EvalRun.status.in_(["PENDING", "RUNNING"]))
                .values(
                    status="FAILED",
                    error_message="服务重启，任务已中断，请重试",
                    completed_at=datetime.now(timezone.utc),
                )
            )
            if result.rowcount > 0:
                await db.commit()
                logger.info(f"已将 {result.rowcount} 个中断的评测任务标记为 FAILED")
    except Exception as e:
        logger.warning(f"恢复评测任务失败（非致命）: {e}")


# ==================== 应用生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理器

    yield 之前 = 应用启动时执行（初始化资源）
    yield 之后 = 应用关闭时执行（释放资源）

    这里只做日志打印，实际的数据库连接池采用"惰性初始化"模式
    （首次请求时才创建），因此不需要在启动时显式初始化。
    """
    settings = get_settings()
    logger.info(f"AgentScope 启动中... 环境: {settings.app_env}")
    logger.info(f"PostgreSQL: {settings.postgres_host}:{settings.postgres_port}")
    logger.info(f"ClickHouse: {settings.clickhouse_host}:{settings.clickhouse_port}")
    logger.info(f"Redis: {settings.redis_host}:{settings.redis_port}")

    # 恢复服务中断时卡住的评测任务
    await _recover_stale_eval_runs()

    yield  # <-- 应用运行中，处理请求 -->

    # 应用关闭时，释放所有连接池
    logger.info("AgentScope 正在关闭...")
    from app.core.database import close_engine
    from app.core.clickhouse import close_clickhouse
    from app.core.redis import close_redis
    await close_engine()       # 关闭 PostgreSQL 连接池
    close_clickhouse()          # 关闭 ClickHouse 连接
    await close_redis()         # 关闭 Redis 连接
    # 关闭共享 HTTP 客户端
    from app.services.agent_adapter import AgentAdapter
    from app.services.llm_client import close_all_llm_clients
    await AgentAdapter.close_client()
    await close_all_llm_clients()
    logger.info("所有连接池已关闭")


# ==================== 应用工厂函数 ====================

def create_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用实例

    这是整个后端的核心配置函数，按顺序完成：
      1. 创建 FastAPI 实例
      2. 添加 CORS 中间件（允许前端跨域请求）
      3. 添加请求日志中间件（记录每个请求的耗时和状态码）
      4. 注册全局异常处理器（确保所有错误都返回统一格式）
      5. 注册所有 API 路由
    """
    settings = get_settings()

    # 创建 FastAPI 实例
    app = FastAPI(
        title=settings.app_name,                                    # API 文档标题
        version="0.1.0",                                           # 版本号
        description="AgentScope - 企业级 AI Agent 评测与可观测性平台",  # API 文档描述
        docs_url="/api/docs" if settings.app_debug else None,      # Swagger UI 地址（仅开发环境）
        redoc_url="/api/redoc" if settings.app_debug else None,    # ReDoc 地址（仅开发环境）
        lifespan=lifespan,                                         # 生命周期管理器
    )

    # ---- 中间件 ----

    # CORS 跨域中间件：允许前端（localhost:5173）访问后端（localhost:8000）
    # 开发环境允许所有来源，生产环境只允许配置的域名
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_debug else settings.cors_origins,
        allow_credentials=True,     # 允许携带 Cookie
        allow_methods=["*"],        # 允许所有 HTTP 方法
        allow_headers=["*"],        # 允许所有请求头
    )

    # 请求日志中间件：记录每个请求的 method、path、状态码、耗时
    from app.core.middleware import RequestLoggingMiddleware
    app.add_middleware(RequestLoggingMiddleware)

    # ---- 全局异常处理器 ----
    # 确保所有异常（业务异常、参数校验异常、未知异常）都返回统一的 JSON 格式
    from fastapi.exceptions import RequestValidationError
    from pydantic import ValidationError
    from app.core.exceptions import AppException
    from app.core.exception_handlers import (
        app_exception_handler,          # 业务异常 → 统一错误响应
        pydantic_validation_handler,    # Pydantic 校验异常 → 统一错误响应
        unhandled_exception_handler,    # 未知异常 → 500 错误响应
        validation_exception_handler,   # FastAPI 参数校验异常 → 统一错误响应
    )
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ---- 注册路由 ----
    register_routers(app)

    return app


# ==================== 路由注册 ====================

def register_routers(app: FastAPI):
    """
    注册所有 API 路由模块

    每个路由模块对应一个业务领域：
      - health:     健康检查（无需认证）
      - auth:       认证（注册/登录/API Key 管理）
      - projects:   项目管理（CRUD + 成员管理）
      - agents:     Agent 管理（注册/更新/删除）
      - datasets:   数据集管理（CRUD + 条目 + 导入导出）
      - traces:     Trace 管理（上报 + 查询，JWT 认证）
      - sdk:        SDK 接口（上报 + 健康检查，API Key 认证）
      - evaluations:评测管理（创建/执行/统计）
      - bad_cases:  Bad Case 管理（标记/更新/统计）

    所有路由统一挂载在 /api/v1 前缀下
    """
    from app.api.health import router as health_router
    app.include_router(health_router, prefix="/api/v1", tags=["健康检查"])

    from app.api.auth import router as auth_router
    app.include_router(auth_router, prefix="/api/v1", tags=["认证"])

    from app.api.projects import router as projects_router
    app.include_router(projects_router, prefix="/api/v1", tags=["项目管理"])

    from app.api.agents import router as agents_router
    app.include_router(agents_router, prefix="/api/v1", tags=["Agent 管理"])

    from app.api.datasets import router as datasets_router
    app.include_router(datasets_router, prefix="/api/v1", tags=["数据集管理"])

    from app.api.traces import router as traces_router
    app.include_router(traces_router, prefix="/api/v1", tags=["Trace 管理"])

    from app.api.sdk import router as sdk_router
    app.include_router(sdk_router, prefix="/api/v1", tags=["SDK 接口"])

    from app.api.evaluations import router as evaluations_router
    app.include_router(evaluations_router, prefix="/api/v1", tags=["评测管理"])

    from app.api.bad_cases import router as bad_cases_router
    app.include_router(bad_cases_router, prefix="/api/v1", tags=["Bad Case 管理"])


# 创建应用实例（uvicorn 启动时使用: uvicorn app.main:app）
app = create_app()
