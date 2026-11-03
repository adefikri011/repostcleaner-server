from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.schemas.activity import ActivityType


def record_activity(
    db: Session,
    *,
    user_id: UUID,
    activity_type: ActivityType,
    entity_type: str,
    entity_id: UUID | None,
    description: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        Activity(
            user_id=user_id,
            activity_type=activity_type,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            activity_metadata=metadata,
        )
    )


def list_activities(
    db: Session,
    *,
    user_id: UUID,
    page: int,
    page_size: int,
    activity_type: ActivityType | None,
    sort: str,
) -> tuple[list[Activity], int]:
    statement: Select[tuple[Activity]] = select(Activity).where(
        Activity.user_id == user_id
    )
    if activity_type is not None:
        statement = statement.where(Activity.activity_type == activity_type)

    total = db.scalar(
        select(func.count()).select_from(statement.subquery())
    ) or 0
    ordering = (
        Activity.created_at.asc() if sort == "oldest" else Activity.created_at.desc()
    )
    statement = statement.order_by(ordering, Activity.id.asc())
    items = list(
        db.scalars(statement.offset((page - 1) * page_size).limit(page_size))
    )
    return items, total
