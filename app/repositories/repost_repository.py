from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.queue_item import QueueItem
from app.models.repost_item import RepostItem
from app.repositories.activity_repository import record_activity
from app.schemas.repost import RepostCreate, RepostStatus, RepostUpdate


def list_reposts(
    db: Session,
    *,
    user_id: UUID,
    page: int,
    page_size: int,
    search: str | None,
    status: RepostStatus | None,
    sort: str,
) -> tuple[list[RepostItem], int]:
    statement: Select[tuple[RepostItem]] = select(RepostItem).where(
        RepostItem.user_id == user_id
    )
    if status is not None:
        statement = statement.where(RepostItem.status == status.value)
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        match = f"%{escaped}%"
        statement = statement.where(
            or_(
                RepostItem.title.ilike(match, escape="\\"),
                RepostItem.description.ilike(match, escape="\\"),
                RepostItem.creator_username.ilike(match, escape="\\"),
                RepostItem.creator_display_name.ilike(match, escape="\\"),
                RepostItem.source_platform.ilike(match, escape="\\"),
            )
        )

    count_statement = select(func.count()).select_from(statement.subquery())
    total = db.scalar(count_statement) or 0

    if sort == "oldest":
        statement = statement.order_by(
            RepostItem.created_at.asc(), RepostItem.id.asc()
        )
    elif sort == "title":
        statement = statement.order_by(
            RepostItem.title.asc().nulls_last(), RepostItem.id.asc()
        )
    else:
        statement = statement.order_by(
            RepostItem.created_at.desc(), RepostItem.id.asc()
        )

    items = list(
        db.scalars(statement.offset((page - 1) * page_size).limit(page_size))
    )
    return items, total


def get_repost(
    db: Session, *, user_id: UUID, repost_id: UUID
) -> RepostItem | None:
    return db.scalar(
        select(RepostItem).where(
            RepostItem.id == repost_id,
            RepostItem.user_id == user_id,
        )
    )


def create_repost(
    db: Session, *, user_id: UUID, payload: RepostCreate
) -> RepostItem:
    repost = RepostItem(user_id=user_id, **payload.model_dump())
    db.add(repost)
    db.flush()
    record_activity(
        db,
        user_id=user_id,
        activity_type="repost_created",
        entity_type="repost_item",
        entity_id=repost.id,
        description="Added item to library",
    )
    db.commit()
    db.refresh(repost)
    return repost


def update_repost(
    db: Session, *, repost: RepostItem, payload: RepostUpdate
) -> RepostItem:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(repost, field, value)
    record_activity(
        db,
        user_id=repost.user_id,
        activity_type="repost_updated",
        entity_type="repost_item",
        entity_id=repost.id,
        description="Updated library item",
    )
    db.commit()
    db.refresh(repost)
    return repost


def delete_repost(db: Session, *, repost: RepostItem) -> None:
    if db.get(QueueItem, (repost.user_id, repost.id)) is not None:
        record_activity(
            db,
            user_id=repost.user_id,
            activity_type="queue_item_removed",
            entity_type="queue_item",
            entity_id=repost.id,
            description="Removed item from review queue after library deletion",
        )
    record_activity(
        db,
        user_id=repost.user_id,
        activity_type="repost_deleted",
        entity_type="repost_item",
        entity_id=repost.id,
        description="Removed item from application library",
    )
    db.delete(repost)
    db.commit()
