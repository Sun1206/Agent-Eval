"""
Agent Schema
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    """注册 Agent 请求"""
    name: str = Field(..., min_length=1, max_length=100, description="Agent 名称")
    version: str = Field(..., min_length=1, max_length=20, description="版本号 (SemVer)")
    description: Optional[str] = Field(None, max_length=2000, description="描述")
    endpoint_url: Optional[str] = Field(None, max_length=500, description="Agent 服务地址")
    config: dict = Field(default_factory=dict, description="Agent 配置 (JSON)")


class AgentUpdate(BaseModel):
    """更新 Agent 请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Agent 名称")
    version: Optional[str] = Field(None, min_length=1, max_length=20, description="版本号")
    description: Optional[str] = Field(None, max_length=2000, description="描述")
    endpoint_url: Optional[str] = Field(None, max_length=500, description="Agent 服务地址")
    config: Optional[dict] = Field(None, description="Agent 配置")


class AgentResponse(BaseModel):
    """Agent 响应"""
    id: UUID
    project_id: UUID
    name: str
    version: str
    description: Optional[str] = None
    endpoint_url: Optional[str] = None
    config: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True