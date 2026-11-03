from math import ceil
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.repost_item import RepostItem
from app.repositories import repost_repository
from app.schemas.repost import (
    RepostCreate,
    RepostList,
    RepostResponse,
    RepostStatus,
    RepostUpdate,
)


class RepostNotFoundError(Exception):
    pass


def list_user_reposts(
    db: Session,
    *,
    user_id: UUID,
    page: int,
    page_size: int,
    search: str | None,
    status: RepostStatus | None,
    sort: str,
) -> RepostList:
    items, total = repost_repository.list_reposts(
        db,
        user_id=user_id,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        sort=sort,
    )
    return RepostList(
        items=[RepostResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total else 0,
    )


def get_user_repost(
    db: Session, *, user_id: UUID, repost_id: UUID
) -> RepostItem:
    repost = repost_repository.get_repost(
        db, user_id=user_id, repost_id=repost_id
    )
    if repost is None:
        raise RepostNotFoundError
    return repost


def create_user_repost(
    db: Session, *, user_id: UUID, payload: RepostCreate
) -> RepostItem:
    return repost_repository.create_repost(db, user_id=user_id, payload=payload)


def update_user_repost(
    db: Session,
    *,
    user_id: UUID,
    repost_id: UUID,
    payload: RepostUpdate,
) -> RepostItem:
    repost = get_user_repost(db, user_id=user_id, repost_id=repost_id)
    return repost_repository.update_repost(db, repost=repost, payload=payload)


def delete_user_repost(
    db: Session, *, user_id: UUID, repost_id: UUID
) -> None:
    repost = get_user_repost(db, user_id=user_id, repost_id=repost_id)
    repost_repository.delete_repost(db, repost=repost)
