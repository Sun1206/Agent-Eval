"""
认证路由 — 注册 / 登录 / 刷新 / 获取当前用户 / API Key 管理
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RegisterRequest,
    TokenRefreshResponse,
    UserResponse,
)
from app.schemas.common import BaseResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["认证"])


# ==================== 注册 / 登录 ====================

@router.post("/register", response_model=BaseResponse[LoginResponse])
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户注册"""
    result = await AuthService.register(db, data)
    return BaseResponse.ok(result, "注册成功")


@router.post("/login", response_model=BaseResponse[LoginResponse])
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户登录"""
    result = await AuthService.login(db, data)
    return BaseResponse.ok(result, "登录成功")


# ==================== Token 管理 ====================

@router.post("/refresh", response_model=BaseResponse[TokenRefreshResponse])
async def refresh_token(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """刷新 Token"""
    result = await AuthService.refresh(db, data.refresh_token)
    return BaseResponse.ok(result, "Token 已刷新")


@router.get("/me", response_model=BaseResponse[UserResponse])
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """获取当前用户信息"""
    result = await AuthService.get_me(current_user)
    return BaseResponse.ok(result)


# ==================== API Key 管理 ====================

@router.post("/api-keys", response_model=BaseResponse[ApiKeyCreateResponse])
async def create_api_key(
    data: ApiKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建 API Key（完整 Key 仅此时返回）"""
    result = await AuthService.create_api_key(db, current_user.id, data)
    return BaseResponse.ok(result, "API Key 创建成功")


@router.get("/api-keys", response_model=BaseResponse[list[ApiKeyResponse]])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出 API Key（不返回完整 Key）"""
    result = await AuthService.list_api_keys(db, current_user.id)
    return BaseResponse.ok(result)


@router.delete("/api-keys/{key_id}", response_model=BaseResponse[None])
async def revoke_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """吊销 API Key"""
    from uuid import UUID
    await AuthService.revoke_api_key(db, current_user.id, UUID(key_id))
    return BaseResponse.ok(None, "API Key 已吊销")