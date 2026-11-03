from uuid import UUID

from sqlalchemy.orm import Session

from app.models.repost_item import RepostItem
from app.repositories import queue_repository


class QueueItemNotFoundError(Exception):
    pass


def list_user_queue(db: Session, *, user_id: UUID) -> list[RepostItem]:
    return queue_repository.list_queue(db, user_id=user_id)


def add_user_queue_items(
    db: Session, *, user_id: UUID, repost_ids: list[UUID]
) -> list[RepostItem]:
    unique_ids = list(dict.fromkeys(repost_ids))
    items = queue_repository.add_items(
        db, user_id=user_id, repost_ids=unique_ids
    )
    if items is None:
        raise QueueItemNotFoundError
    return items


def remove_user_queue_item(
    db: Session, *, user_id: UUID, repost_id: UUID
) -> None:
    if not queue_repository.remove_item(
        db, user_id=user_id, repost_id=repost_id
    ):
        raise QueueItemNotFoundError


def clear_user_queue(db: Session, *, user_id: UUID) -> int:
    return queue_repository.clear_queue(db, user_id=user_id)
