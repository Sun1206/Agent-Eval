"""
认证模块 Pydantic Schema
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ==================== 请求 Schema ====================

class RegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    display_name: Optional[str] = Field(None, max_length=100, description="显示名称")

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("用户名只能包含字母、数字、下划线和连字符")
        return v.lower()


class LoginRequest(BaseModel):
    """用户登录请求（支持用户名或邮箱）"""
    login: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class RefreshRequest(BaseModel):
    """Token 刷新请求"""
    refresh_token: str = Field(..., description="刷新令牌")


# ==================== 响应 Schema ====================

class UserResponse(BaseModel):
    """用户信息响应"""
    id: UUID
    username: str
    email: str
    display_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """登录/注册响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenRefreshResponse(BaseModel):
    """Token 刷新响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ==================== API Key Schema ====================

class ApiKeyCreateRequest(BaseModel):
    """创建 API Key 请求"""
    name: str = Field(..., min_length=1, max_length=100, description="Key 名称")
    expires_at: Optional[datetime] = Field(None, description="过期时间（可选，不设则永不过期）")


class ApiKeyResponse(BaseModel):
    """API Key 列表响应（不返回完整 Key）"""
    id: UUID
    name: str
    key_prefix: str = Field(..., description="Key 前缀（agev_xxxx...）用于识别")
    is_active: bool
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyCreateResponse(ApiKeyResponse):
    """API Key 创建响应（返回完整 Key，仅此一次）"""
    full_key: str = Field(..., description="完整 API Key，请立即保存，后续无法再查看")