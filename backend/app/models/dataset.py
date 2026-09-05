"""
数据集与数据集条目 ORM 模型
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, AuditMixin, UUIDMixin


class Dataset(Base, UUIDMixin, AuditMixin):
    """数据集表"""

    __tablename__ = "datasets"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目",
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="数据集名称"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="描述"
    )
    tags: Mapped[list] = mapped_column(
        ARRAY(String(50)),
        server_default="{}",
        default=list,
        comment="标签数组",
    )
    item_count: Mapped[int] = mapped_column(
        Integer, server_default="0", comment="数据条目数（冗余计数）"
    )

    # 关联
    items: Mapped[list["DatasetItem"]] = relationship(
        "DatasetItem", back_populates="dataset", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Dataset(id={self.id}, name={self.name})>"


class DatasetItem(Base, UUIDMixin):
    """数据集条目表"""

    __tablename__ = "dataset_items"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属数据集",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, server_default="0", comment="排序序号"
    )
    input: Mapped[str] = mapped_column(Text, nullable=False, comment="用户输入/问题")
    expected_output: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="期望输出/参考答案"
    )
    context: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="上下文信息"
    )
    tags: Mapped[list] = mapped_column(
        ARRAY(String(50)),
        server_default="{}",
        default=list,
        comment="条目级标签",
    )
    item_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default="{}", default=dict, comment="扩展元数据"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间",
    )

    # 关联
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="items")

    def __repr__(self) -> str:
        return f"<DatasetItem(id={self.id}, dataset_id={self.dataset_id})>"