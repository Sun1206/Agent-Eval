"""
用户与 API Key ORM 模型
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin):
    """用户表"""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="用户名"
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, comment="邮箱"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希 (bcrypt)"
    )
    display_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="显示名称"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=func.true(), comment="是否激活"
    )

    # 关联
    api_keys: Mapped[list["ApiKey"]] = relationship(
        "ApiKey", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"


class ApiKey(Base, UUIDMixin):
    """API Key 表"""

    __tablename__ = "api_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属用户",
    )
    key_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="API Key 哈希 (SHA256)"
    )
    key_prefix: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Key 前缀（agev_xxxx...），用于快速定位"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Key 名称"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=func.true(), comment="是否有效"
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最后使用时间"
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="过期时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间",
    )

    # 关联
    user: Mapped["User"] = relationship("User", back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, name={self.name})>"