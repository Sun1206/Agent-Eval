"""
健康检查 API 路由
"""
from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """服务健康检查"""
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "0.1.0",
        "environment": settings.app_env,
    }


@router.get("/health/ready")
async def readiness_check():
    """就绪检查（可在此扩展数据库连接检查）"""
    return {"status": "ready"}