"""
Trace/轨迹表 ORM 模型
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class Trace(Base, UUIDMixin):
    """Trace/轨迹表（PG 中存储元数据，Detail 在 ClickHouse）"""

    __tablename__ = "traces"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目",
    )
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联 Agent",
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="会话 ID"
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="终端用户 ID"
    )
    input: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="用户输入"
    )
    output: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="最终输出"
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="开始时间"
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="结束时间"
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="总耗时（毫秒）"
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, server_default="0", comment="总 Token 用量"
    )
    total_cost: Mapped[float] = mapped_column(
        Numeric(10, 6), server_default="0", comment="总成本（美元）"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="SUCCESS",
        comment="SUCCESS/ERROR",
    )
    spans: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default="'[]'",
        default=list,
        comment="Span 数组（树形结构）",
    )
    trace_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default="{}", default=dict, comment="扩展元数据"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="入库时间",
    )

    def __repr__(self) -> str:
        return f"<Trace(id={self.id}, project_id={self.project_id}, status={self.status})>"