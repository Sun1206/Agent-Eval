"""
Agent 注册表 ORM 模型
"""
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Agent(Base, UUIDMixin, TimestampMixin):
    """Agent 注册表"""

    __tablename__ = "agents"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目",
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Agent 名称"
    )
    version: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="版本号 (SemVer)"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="描述"
    )
    endpoint_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="Agent 服务地址"
    )
    config: Mapped[dict] = mapped_column(
        JSONB, server_default="{}", default=dict, comment="Agent 配置"
    )

    # 关联
    project: Mapped["Project"] = relationship("Project", back_populates="agents")

    def __repr__(self) -> str:
        return f"<Agent(id={self.id}, name={self.name}, version={self.version})>"