"""
项目与项目成员 ORM 模型
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Project(Base, UUIDMixin, TimestampMixin):
    """项目表"""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="项目名称"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="项目描述"
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="创建者",
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, server_default=func.false(), comment="软删除标记"
    )

    # 关联
    members: Mapped[list["ProjectMember"]] = relationship(
        "ProjectMember", back_populates="project", cascade="all, delete-orphan"
    )
    agents: Mapped[list["Agent"]] = relationship(
        "Agent", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name})>"


class ProjectMember(Base, UUIDMixin):
    """项目成员表"""

    __tablename__ = "project_members"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="成员用户",
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="member",
        comment="角色: owner/admin/member/viewer",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="加入时间",
    )

    # 关联
    project: Mapped["Project"] = relationship("Project", back_populates="members")

    def __repr__(self) -> str:
        return f"<ProjectMember(project_id={self.project_id}, user_id={self.user_id})>"