"""Persist user-owned activity history.

Revision ID: 20261103_04
Revises: 20261103_03
Create Date: 2026-11-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261103_04"
down_revision: Union[str, None] = "20261103_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True).with_variant(
        postgresql.UUID(as_uuid=True), "postgresql"
    )
    op.create_table(
        "activities",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("activity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", uuid_type, nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "activity_type IN ("
            "'repost_created', 'repost_updated', 'repost_deleted', "
            "'queue_item_added', 'queue_item_removed')",
            name="ck_activities_valid_activity_type",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_activities_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_activities"),
    )
    op.create_index(
        "ix_activities_user_created",
        "activities",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_activities_user_type_created",
        "activities",
        ["user_id", "activity_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_activities_user_type_created", table_name="activities")
    op.drop_index("ix_activities_user_created", table_name="activities")
    op.drop_table("activities")
