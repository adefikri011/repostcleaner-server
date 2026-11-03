from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.queue_item import QueueItem
from app.models.repost_item import RepostItem
from app.repositories.activity_repository import record_activity


def list_queue(db: Session, *, user_id: UUID) -> list[RepostItem]:
    statement = (
        select(RepostItem)
        .join(
            QueueItem,
            (QueueItem.repost_item_id == RepostItem.id)
            & (QueueItem.user_id == user_id),
        )
        .where(RepostItem.user_id == user_id)
        .order_by(QueueItem.created_at.asc(), RepostItem.id.asc())
    )
    return list(db.scalars(statement))


def add_items(
    db: Session, *, user_id: UUID, repost_ids: list[UUID]
) -> list[RepostItem] | None:
    reposts = list(
        db.scalars(
            select(RepostItem).where(
                RepostItem.user_id == user_id,
                RepostItem.id.in_(repost_ids),
            )
        )
    )
    if len(reposts) != len(repost_ids):
        return None

    already_queued = set(
        db.scalars(
            select(QueueItem.repost_item_id).where(
                QueueItem.user_id == user_id,
                QueueItem.repost_item_id.in_(repost_ids),
            )
        )
    )
    new_ids = [
        repost_id for repost_id in repost_ids if repost_id not in already_queued
    ]
    if new_ids:
        db.add_all(
            QueueItem(user_id=user_id, repost_item_id=repost_id)
            for repost_id in new_ids
        )
        for repost_id in new_ids:
            record_activity(
                db,
                user_id=user_id,
                activity_type="queue_item_added",
                entity_type="queue_item",
                entity_id=repost_id,
                description="Added item to review queue",
            )
        db.commit()
    return list_queue(db, user_id=user_id)


def remove_item(
    db: Session, *, user_id: UUID, repost_id: UUID
) -> bool:
    result = db.execute(
        delete(QueueItem).where(
            QueueItem.user_id == user_id,
            QueueItem.repost_item_id == repost_id,
        )
    )
    if result.rowcount == 0:
        db.rollback()
        return False
    record_activity(
        db,
        user_id=user_id,
        activity_type="queue_item_removed",
        entity_type="queue_item",
        entity_id=repost_id,
        description="Removed item from review queue",
    )
    db.commit()
    return True


def clear_queue(db: Session, *, user_id: UUID) -> int:
    removed_ids = list(
        db.scalars(
            delete(QueueItem)
            .where(QueueItem.user_id == user_id)
            .returning(QueueItem.repost_item_id)
        )
    )
    for repost_id in removed_ids:
        record_activity(
            db,
            user_id=user_id,
            activity_type="queue_item_removed",
            entity_type="queue_item",
            entity_id=repost_id,
            description="Removed item from review queue",
        )
    db.commit()
    return len(removed_ids)
