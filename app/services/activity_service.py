from math import ceil
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories import activity_repository
from app.schemas.activity import ActivityList, ActivityResponse, ActivityType


def list_user_activities(
    db: Session,
    *,
    user_id: UUID,
    page: int,
    page_size: int,
    activity_type: ActivityType | None,
    sort: str,
) -> ActivityList:
    items, total = activity_repository.list_activities(
        db,
        user_id=user_id,
        page=page,
        page_size=page_size,
        activity_type=activity_type,
        sort=sort,
    )
    return ActivityList(
        items=[ActivityResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )
