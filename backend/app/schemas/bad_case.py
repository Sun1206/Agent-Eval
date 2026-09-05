"""
Bad Case Schema — 创建 / 更新 / 响应
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ==================== 枚举 ====================

class BadCaseTag(str, Enum):
    """Bad Case 标签枚举"""
    HALLUCINATION = "hallucination"
    ERROR = "error"
    OMISSION = "omission"
    TIMEOUT = "timeout"
    OTHER = "other"


class BadCaseStatus(str, Enum):
    """Bad Case 状态枚举"""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


# ==================== 创建 ====================

class BadCaseCreate(BaseModel):
    """标记 Bad Case 请求"""
    trace_id: UUID = Field(..., description="关联的 Trace ID")
    tag: BadCaseTag = Field(..., description="标签: hallucination/error/omission/timeout/other")
    description: Optional[str] = Field(None, description="问题描述")
    assignee_id: Optional[UUID] = Field(None, description="负责人 ID")


# ==================== 更新 ====================

class BadCaseUpdate(BaseModel):
    """更新 Bad Case 请求"""
    status: Optional[BadCaseStatus] = Field(None, description="状态: open/in_progress/resolved/closed")
    assignee_id: Optional[UUID] = Field(None, description="负责人 ID")
    resolution: Optional[str] = Field(None, description="解决方案")


# ==================== 响应 ====================

class BadCaseResponse(BaseModel):
    """Bad Case 响应"""
    id: UUID
    project_id: UUID
    trace_id: UUID
    tag: str
    description: Optional[str] = None
    status: str
    assignee_id: Optional[UUID] = None
    resolution: Optional[str] = None
    marked_by: UUID
    marked_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True