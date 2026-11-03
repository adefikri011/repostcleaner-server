from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base


class RepostItem(Base):
    __tablename__ = "repost_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('saved', 'archived')",
            name="valid_status",
        ),
        UniqueConstraint(
            "user_id",
            "source_platform",
            "source_id",
            name="uq_repost_items_user_platform_source",
        ),
        Index("ix_repost_items_user_created", "user_id", "created_at"),
        Index("ix_repost_items_user_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_platform: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    original_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    creator_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    creator_display_name: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="saved", server_default="saved"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="repost_items")
