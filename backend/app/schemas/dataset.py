"""
数据集 Schema
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, AliasChoices, field_validator


# ==================== 数据集 CRUD ====================

class DatasetCreate(BaseModel):
    """创建数据集请求"""
    name: str = Field(..., min_length=1, max_length=200, description="数据集名称")
    description: Optional[str] = Field(None, max_length=2000, description="描述")
    tags: list[str] = Field(default_factory=list, description="标签")


class DatasetUpdate(BaseModel):
    """更新数据集请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="数据集名称")
    description: Optional[str] = Field(None, max_length=2000, description="描述")
    tags: Optional[list[str]] = Field(None, description="标签")


class DatasetResponse(BaseModel):
    """数据集响应"""
    id: UUID
    project_id: UUID
    name: str
    description: Optional[str] = None
    tags: list[str] = []
    item_count: int = 0
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== 数据集条目 CRUD ====================

class DatasetItemCreate(BaseModel):
    """创建数据集条目请求"""
    input: str = Field(..., min_length=1, description="用户输入/问题")
    expected_output: Optional[str] = Field(None, description="期望输出/参考答案")
    context: Optional[str] = Field(None, description="上下文信息")
    tags: list[str] = Field(default_factory=list, description="条目级标签")
    metadata: dict = Field(default_factory=dict, description="扩展元数据")
    sort_order: int = Field(default=0, description="排序序号")

    @field_validator("input")
    @classmethod
    def input_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("input 不能为空")
        return v


class DatasetItemUpdate(BaseModel):
    """更新数据集条目请求"""
    input: Optional[str] = Field(None, min_length=1, description="用户输入/问题")
    expected_output: Optional[str] = Field(None, description="期望输出/参考答案")
    context: Optional[str] = Field(None, description="上下文信息")
    tags: Optional[list[str]] = Field(None, description="条目级标签")
    metadata: Optional[dict] = Field(None, description="扩展元数据")
    sort_order: Optional[int] = Field(None, description="排序序号")


class DatasetItemResponse(BaseModel):
    """数据集条目响应"""
    id: UUID
    dataset_id: UUID
    sort_order: int = 0
    input: str
    expected_output: Optional[str] = None
    context: Optional[str] = None
    tags: list[str] = []
    metadata: dict = Field(default={}, validation_alias=AliasChoices('item_metadata', 'metadata'))
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 批量删除 ====================

class BatchDeleteRequest(BaseModel):
    """批量删除条目请求"""
    item_ids: list[UUID] = Field(..., min_length=1, description="要删除的条目ID列表")


class BatchDeleteResponse(BaseModel):
    """批量删除条目响应"""
    deleted: int = Field(..., description="成功删除的条目数")


# ==================== 导入结果 ====================

class ImportResultResponse(BaseModel):
    """导入结果响应"""
    total: int = Field(..., description="解析到的总条目数")
    imported: int = Field(..., description="成功导入数")
    skipped: int = Field(default=0, description="跳过的无效条目数")
    errors: list[str] = Field(default_factory=list, description="错误详情")