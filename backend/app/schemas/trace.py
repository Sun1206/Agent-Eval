"""
Trace 数据模型 Pydantic Schema

Span 树形结构:
  顶层 Span 的 parent_span_id 为 None
  子 Span 通过 parent_span_id 指向父 Span
  同一 TraceReport 内所有 span_id 必须唯一
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


# Python 3.10 兼容的 StrEnum（3.11+ 内置，3.10 需手动定义）
class StrEnum(str, Enum):
    pass


# ==================== 枚举 ====================

class SpanType(StrEnum):
    """Span 类型"""
    CHAIN = "chain"              # 编排链
    LLM_CALL = "llm_call"        # LLM 调用
    TOOL_CALL = "tool_call"      # 工具调用
    RETRIEVAL = "retrieval"      # 检索
    EMBEDDING = "embedding"      # 向量嵌入


class SpanStatus(StrEnum):
    """Span 执行状态"""
    SUCCESS = "success"
    ERROR = "error"


# ==================== Span ====================

class SpanMetadata(BaseModel):
    """Span 扩展元数据"""
    model: Optional[str] = Field(None, description="使用的模型名称")
    token_usage: Optional[dict] = Field(
        None, description="Token 用量, 如 {'prompt': 100, 'completion': 50, 'total': 150}"
    )
    cost: Optional[float] = Field(None, ge=0, description="成本（美元）")


class SpanSchema(BaseModel):
    """单个 Span 结构"""
    span_id: UUID = Field(default_factory=uuid4, description="Span 唯一 ID")
    parent_span_id: Optional[UUID] = Field(None, description="父 Span ID，顶层 Span 为 None")
    type: SpanType = Field(..., description="Span 类型")
    name: str = Field(..., min_length=1, max_length=255, description="Span 名称")
    start_time: datetime = Field(..., description="开始时间 (ISO 8601)")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    status: SpanStatus = Field(default=SpanStatus.SUCCESS, description="执行状态")
    input: Optional[dict] = Field(None, description="输入数据")
    output: Optional[dict] = Field(None, description="输出数据")
    metadata: SpanMetadata = Field(default_factory=SpanMetadata, description="扩展元数据")

    @field_validator("parent_span_id")
    @classmethod
    def self_reference_check(cls, v: Optional[UUID], info) -> Optional[UUID]:
        """校验 parent_span_id 不能等于自身 span_id"""
        span_id = info.data.get("span_id") if info.data else None
        if v is not None and span_id is not None and v == span_id:
            raise ValueError("parent_span_id 不能指向自身")
        return v

    @field_validator("end_time")
    @classmethod
    def end_time_after_start(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """校验 end_time >= start_time"""
        if v is not None:
            start_time = info.data.get("start_time") if info.data else None
            if start_time is not None and v < start_time:
                raise ValueError("end_time 不能早于 start_time")
        return v


# ==================== Trace 上报请求 ====================

class TraceReportRequest(BaseModel):
    """
    SDK 上报 Trace 的完整请求体

    示例:
    {
      "trace_id": "uuid",
      "project_id": "uuid",
      "agent_id": "uuid",
      "session_id": "sess_001",
      "user_id": "user_001",
      "input": {"question": "你好"},
      "output": {"answer": "你好！"},
      "start_time": "2026-01-01T00:00:00Z",
      "end_time": "2026-01-01T00:00:05Z",
      "duration_ms": 5000,
      "total_tokens": 150,
      "total_cost": 0.001,
      "status": "SUCCESS",
      "spans": [...],
      "tags": ["qa"],
      "metadata": {}
    }
    """
    trace_id: UUID = Field(..., description="Trace 唯一 ID")
    project_id: UUID = Field(..., description="所属项目 ID")
    agent_id: Optional[UUID] = Field(None, description="关联 Agent ID")
    session_id: Optional[str] = Field(None, max_length=255, description="会话 ID")
    user_id: Optional[str] = Field(None, max_length=255, description="终端用户 ID")

    input: Optional[str] = Field(None, description="用户输入（文本）")
    output: Optional[str] = Field(None, description="最终输出（文本）")
    start_time: datetime = Field(..., description="Trace 开始时间")
    end_time: Optional[datetime] = Field(None, description="Trace 结束时间")
    duration_ms: Optional[int] = Field(None, ge=0, description="总耗时（毫秒）")
    total_tokens: int = Field(default=0, ge=0, description="总 Token 用量")
    total_cost: float = Field(default=0.0, ge=0, description="总成本（美元）")
    status: str = Field(default="SUCCESS", description="SUCCESS 或 ERROR")

    spans: list[SpanSchema] = Field(default_factory=list, description="Span 数组")
    tags: list[str] = Field(default_factory=list, description="标签")
    metadata: dict = Field(default_factory=dict, description="扩展元数据")

    # ==================== Span 树形结构校验 ====================

    @model_validator(mode="after")
    def validate_span_tree(self):
        """校验 Span 树形结构的合法性"""
        spans = self.spans
        if not spans:
            return self

        # 1. span_id 全局唯一
        span_ids = [s.span_id for s in spans]
        if len(span_ids) != len(set(span_ids)):
            raise ValueError("spans 中存在重复的 span_id")

        span_id_set = set(span_ids)

        # 2. parent_span_id 必须指向同一个请求中的有效 span_id
        for span in spans:
            if span.parent_span_id is not None and span.parent_span_id not in span_id_set:
                raise ValueError(
                    f"Span '{span.span_id}' 的 parent_span_id "
                    f"'{span.parent_span_id}' 在 spans 中不存在"
                )

        # 3. 至少有一个顶层 Span（parent_span_id 为 None）
        root_spans = [s for s in spans if s.parent_span_id is None]
        if not root_spans:
            raise ValueError("spans 中必须至少有一个顶层 Span（parent_span_id=None）")

        # 4. 检测循环引用
        parent_map = {s.span_id: s.parent_span_id for s in spans}
        for span_id in span_ids:
            visited = set()
            current = span_id
            while current is not None:
                if current in visited:
                    raise ValueError(f"spans 中存在循环引用，涉及 span_id: {span_id}")
                visited.add(current)
                current = parent_map.get(current)

        # 5. 校验时间一致性：所有 Span 时间在 Trace 时间范围内
        for span in spans:
            if span.start_time < self.start_time:
                raise ValueError(
                    f"Span '{span.span_id}' 的 start_time 早于 Trace start_time"
                )
            if self.end_time and span.end_time and span.end_time > self.end_time:
                raise ValueError(
                    f"Span '{span.span_id}' 的 end_time 晚于 Trace end_time"
                )

        return self

    @field_validator("end_time")
    @classmethod
    def end_time_after_start(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """校验 Trace 层面 end_time >= start_time"""
        if v is not None:
            start_time = info.data.get("start_time") if info.data else None
            if start_time is not None and v < start_time:
                raise ValueError("Trace end_time 不能早于 start_time")
        return v


# ==================== Trace 查询响应 ====================

class TraceResponse(BaseModel):
    """
    单条 Trace 查询响应（含完整 spans 数组）

    与 TraceReportRequest 结构一致，额外包含 id 和 created_at
    """
    id: UUID = Field(..., description="Trace UUID")
    trace_id: UUID = Field(..., description="Trace 唯一 ID（与上报时一致）")
    project_id: UUID
    agent_id: Optional[UUID] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    input: Optional[str] = None
    output: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    total_tokens: int = 0
    total_cost: float = 0.0
    status: str = "SUCCESS"
    spans: list[SpanSchema] = Field(default_factory=list, description="完整 Span 数组")
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    created_at: Optional[datetime] = Field(None, description="入库时间")


class TraceListResponse(BaseModel):
    """
    Trace 列表项（不含完整 spans，减少传输量）

    用于列表页展示，只返回汇总信息。
    """
    id: UUID
    trace_id: UUID
    project_id: UUID
    agent_id: Optional[UUID] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    input: Optional[str] = None
    output: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    total_tokens: int = 0
    total_cost: float = 0.0
    status: str = "SUCCESS"
    span_count: int = Field(default=0, description="Span 数量（不含完整数据）")
    tags: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None