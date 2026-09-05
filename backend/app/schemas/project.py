"""
项目 Schema
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """创建项目请求"""
    name: str = Field(..., min_length=1, max_length=100, description="项目名称")
    description: Optional[str] = Field(None, max_length=2000, description="项目描述")


class ProjectUpdate(BaseModel):
    """更新项目请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="项目名称")
    description: Optional[str] = Field(None, max_length=2000, description="项目描述")


class ProjectResponse(BaseModel):
    """项目响应"""
    id: UUID
    name: str
    description: Optional[str] = None
    owner_id: UUID
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== 项目成员 ====================

class MemberAddRequest(BaseModel):
    """添加项目成员请求"""
    user_id: UUID = Field(..., description="用户 ID")
    role: str = Field(default="member", pattern="^(admin|member|viewer)$", description="角色: admin/member/viewer")


class MemberResponse(BaseModel):
    """项目成员响应"""
    id: UUID
    project_id: UUID
    user_id: UUID
    role: str
    username: Optional[str] = None
    created_at: Optional[datetime] = None