"""
评测 Schema — 创建请求 / 响应 / 统计摘要
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ==================== 评分配置 ====================

class JudgeConfigSchema(BaseModel):
    """LLM Judge 评分配置"""
    provider: str = Field(default="openai", description="LLM 提供商")
    model: str = Field(default="gpt-4o-mini", description="评分模型")
    prompt_template: str = Field(
        default="请根据以下维度对 Agent 输出进行评分...",
        description="评分 Prompt 模板",
    )
    dimensions: list[str] = Field(
        default_factory=lambda: ["准确性", "完整性", "相关性"],
        description="评分维度列表",
    )
    weights: dict[str, float] = Field(
        default_factory=dict,
        description="各维度权重，key=维度名, value=权重(0-1)，总和应为1",
    )


# ==================== 创建请求 ====================

class EvalRunCreate(BaseModel):
    """创建评测任务"""
    dataset_id: UUID = Field(..., description="数据集 ID")
    agent_id: UUID = Field(..., description="被评测 Agent ID")
    name: Optional[str] = Field(None, max_length=200, description="任务名称（可选）")
    judge_config: JudgeConfigSchema = Field(
        default_factory=JudgeConfigSchema, description="评分配置"
    )
    concurrency: int = Field(default=5, ge=1, le=20, description="并发数")

    class Config:
        json_schema_extra = {
            "example": {
                "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
                "agent_id": "660e8400-e29b-41d4-a716-446655440001",
                "name": "客服 Agent 评测 v1",
                "concurrency": 5,
                "judge_config": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "dimensions": ["准确性", "完整性", "相关性", "安全性"],
                    "weights": {"准确性": 0.4, "完整性": 0.3, "相关性": 0.2, "安全性": 0.1},
                },
            }
        }


# ==================== 评测任务列表项 ====================

class EvalRunListItem(BaseModel):
    """评测任务列表项（精简字段）"""
    id: UUID
    project_id: UUID
    dataset_id: UUID
    agent_id: UUID
    name: Optional[str] = None
    status: str
    concurrency: int
    total_items: int
    completed_items: int
    failed_items: int
    avg_score: Optional[float] = None
    pass_rate: Optional[float] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """处理 Numeric → float 转换"""
        if obj is not None:
            if hasattr(obj, 'avg_score') and obj.avg_score is not None:
                obj.avg_score = float(obj.avg_score)
            if hasattr(obj, 'pass_rate') and obj.pass_rate is not None:
                obj.pass_rate = float(obj.pass_rate)
        return super().model_validate(obj, **kwargs)


# ==================== 评测任务详情 ====================

class EvalRunDetail(BaseModel):
    """评测任务详情（含 judge_config）"""
    id: UUID
    project_id: UUID
    dataset_id: UUID
    agent_id: UUID
    name: Optional[str] = None
    status: str
    judge_config: JudgeConfigSchema = Field(default_factory=JudgeConfigSchema)
    concurrency: int
    total_items: int
    completed_items: int
    failed_items: int
    avg_score: Optional[float] = None
    pass_rate: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """处理 Numeric → float 转换"""
        if obj is not None:
            if hasattr(obj, 'avg_score') and obj.avg_score is not None:
                obj.avg_score = float(obj.avg_score)
            if hasattr(obj, 'pass_rate') and obj.pass_rate is not None:
                obj.pass_rate = float(obj.pass_rate)
        return super().model_validate(obj, **kwargs)


# ==================== 评测结果 ====================

class EvalResultItem(BaseModel):
    """单条评测结果"""
    id: UUID
    eval_run_id: UUID
    dataset_item_id: UUID
    sort_order: int
    agent_input: str
    agent_output: Optional[str] = None
    total_score: Optional[float] = None
    dimension_scores: dict = Field(default_factory=dict)
    judge_reason: Optional[str] = None
    status: str
    trace_id: Optional[UUID] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    token_usage: dict = Field(default_factory=dict)
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """重写 model_validate，处理 Numeric → float 转换"""
        if obj is not None and hasattr(obj, 'total_score') and obj.total_score is not None:
            obj.total_score = float(obj.total_score)
        return super().model_validate(obj, **kwargs)


# ==================== 统计摘要 ====================

class EvalStatsResponse(BaseModel):
    """评测任务统计摘要"""
    total_items: int = 0
    success_items: int = 0
    failure_items: int = 0
    pass_rate: Optional[float] = None
    avg_score: Optional[float] = None
    dimension_avgs: dict = Field(
        default_factory=dict,
        description="各维度平均分",
    )
    score_distribution: dict = Field(
        default_factory=dict,
        description="得分分布: {'0-20': 0, '21-40': 1, '41-60': 3, '61-80': 10, '81-100': 5}",
    )
    avg_duration_ms: Optional[float] = Field(None, description="平均耗时（毫秒）")


# ==================== 进度查询 ====================

class EvalProgressResponse(BaseModel):
    """评测进度"""
    status: str = "UNKNOWN"
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    avg_score: Optional[float] = None
    pass_rate: Optional[float] = None