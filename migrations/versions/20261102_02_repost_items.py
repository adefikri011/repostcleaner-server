"""Create owner-scoped repost library items.

Revision ID: 20261102_02
Revises: 20261102_01
Create Date: 2026-11-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261102_02"
down_revision: Union[str, None] = "20261102_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True).with_variant(
        postgresql.UUID(as_uuid=True), "postgresql"
    )
    op.create_table(
        "repost_items",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("source_platform", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=200), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=2048), nullable=True),
        sa.Column("original_url", sa.String(length=2048), nullable=True),
        sa.Column("creator_username", sa.String(length=100), nullable=True),
        sa.Column("creator_display_name", sa.String(length=160), nullable=True),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default="saved",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('saved', 'archived')",
            name="valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_repost_items_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_repost_items"),
        sa.UniqueConstraint(
            "user_id",
            "source_platform",
            "source_id",
            name="uq_repost_items_user_platform_source",
        ),
    )
    op.create_index(
        "ix_repost_items_user_created",
        "repost_items",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_repost_items_user_status",
        "repost_items",
        ["user_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_repost_items_user_status", table_name="repost_items")
    op.drop_index("ix_repost_items_user_created", table_name="repost_items")
    op.drop_table("repost_items")
