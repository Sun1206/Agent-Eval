"""
Bad Case 表 ORM 模型
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class BadCase(Base, UUIDMixin, TimestampMixin):
    """Bad Case 表"""

    __tablename__ = "bad_cases"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目",
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="关联的 Trace ID（存储在 ClickHouse，无外键约束）",
    )
    tag: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="标签: hallucination/error/omission/timeout/other",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="问题描述"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="open",
        comment="open/in_progress/resolved/closed",
    )
    assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="负责人",
    )
    resolution: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="解决方案"
    )
    marked_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="标记人",
    )
    marked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="标记时间",
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="解决时间"
    )

    def __repr__(self) -> str:
        return f"<BadCase(id={self.id}, tag={self.tag}, status={self.status})>"