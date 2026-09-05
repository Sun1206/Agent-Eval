"""
SDK 内部数据模型 — 轻量 dataclass，不依赖 Pydantic
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4


class SpanType:
    """Span 类型常量"""
    CHAIN = "chain"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    RETRIEVAL = "retrieval"
    EMBEDDING = "embedding"


class SpanStatus:
    """Span 状态常量"""
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class Span:
    """单个 Span"""
    span_id: UUID = field(default_factory=uuid4)
    parent_span_id: Optional[UUID] = None
    type: str = "chain"
    name: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str = "success"
    input: Optional[dict] = None
    output: Optional[dict] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转为可 JSON 序列化的 dict"""
        return {
            "span_id": str(self.span_id),
            "parent_span_id": str(self.parent_span_id) if self.parent_span_id else None,
            "type": self.type,
            "name": self.name,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "input": self.input,
            "output": self.output,
            "metadata": self.metadata,
        }


@dataclass
class Trace:
    """一次完整的 Trace"""
    trace_id: UUID = field(default_factory=uuid4)
    project_id: str = ""
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    input: Optional[str] = None
    output: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    total_tokens: int = 0
    total_cost: float = 0.0
    status: str = "SUCCESS"
    spans: list[Span] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转为可 JSON 序列化的 dict（符合服务端 TraceReportRequest 格式）"""
        return {
            "trace_id": str(self.trace_id),
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "input": self.input,
            "output": self.output,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "status": self.status,
            "spans": [s.to_dict() for s in self.spans],
            "tags": self.tags,
            "metadata": self.metadata,
        }