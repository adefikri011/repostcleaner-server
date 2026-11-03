"""Persist user-owned review queue entries.

Revision ID: 20261103_03
Revises: 20261102_02
Create Date: 2026-11-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261103_03"
down_revision: Union[str, None] = "20261102_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True).with_variant(
        postgresql.UUID(as_uuid=True), "postgresql"
    )
    op.create_table(
        "queue_items",
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("repost_item_id", uuid_type, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_queue_items_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repost_item_id"],
            ["repost_items.id"],
            name="fk_queue_items_repost_item_id_repost_items",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "repost_item_id", name="pk_queue_items"
        ),
    )
    op.create_index(
        "ix_queue_items_user_created",
        "queue_items",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_queue_items_user_created", table_name="queue_items")
    op.drop_table("queue_items")
