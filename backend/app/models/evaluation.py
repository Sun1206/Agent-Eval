"""
评测任务与评测结果 ORM 模型
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, AuditMixin, UUIDMixin


class EvalRun(Base, UUIDMixin, AuditMixin):
    """评测任务表"""

    __tablename__ = "eval_runs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目",
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="RESTRICT"),
        nullable=False,
        comment="使用的数据集",
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
        comment="被评测的 Agent",
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="任务名称"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="PENDING",
        comment="PENDING/RUNNING/COMPLETED/FAILED/CANCELLED",
    )
    judge_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, comment="评分配置"
    )
    concurrency: Mapped[int] = mapped_column(
        Integer, server_default="5", comment="并发数"
    )
    total_items: Mapped[int] = mapped_column(
        Integer, server_default="0", comment="总用例数"
    )
    completed_items: Mapped[int] = mapped_column(
        Integer, server_default="0", comment="已完成用例数"
    )
    failed_items: Mapped[int] = mapped_column(
        Integer, server_default="0", comment="失败用例数"
    )
    avg_score: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="平均分"
    )
    pass_rate: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="通过率（百分比）"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="开始时间"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="完成时间"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="失败原因"
    )

    def __repr__(self) -> str:
        return f"<EvalRun(id={self.id}, name={self.name}, status={self.status})>"


class EvalResult(Base, UUIDMixin):
    """评测结果表"""

    __tablename__ = "eval_results"

    eval_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属评测任务",
    )
    dataset_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataset_items.id", ondelete="RESTRICT"),
        nullable=False,
        comment="对应的数据集条目",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, server_default="0", comment="执行顺序"
    )
    agent_input: Mapped[str] = mapped_column(
        Text, nullable=False, comment="发送给 Agent 的输入"
    )
    agent_output: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Agent 的输出"
    )
    total_score: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2), nullable=True, comment="总分 (0-100)"
    )
    dimension_scores: Mapped[dict] = mapped_column(
        JSONB, server_default="{}", default=dict, comment="各维度得分"
    )
    judge_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="LLM Judge 评分理由"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="SUCCESS/FAILURE/ERROR/TIMEOUT"
    )
    trace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="关联的 Trace ID（存储在 ClickHouse，无外键约束）",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="错误信息"
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="执行耗时（毫秒）"
    )
    token_usage: Mapped[dict] = mapped_column(
        JSONB, server_default="{}", default=dict, comment="Token 用量"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<EvalResult(id={self.id}, eval_run_id={self.eval_run_id}, status={self.status})>"