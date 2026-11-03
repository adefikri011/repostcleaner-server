from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_authenticated_session, require_csrf
from app.db.session import get_db
from app.models.session import UserSession
from app.models.user import User
from app.models.repost_item import RepostItem
from app.schemas.auth import ApiResponse
from app.schemas.queue import QueueAddRequest, QueueResponse
from app.schemas.repost import RepostResponse
from app.services.queue_service import (
    QueueItemNotFoundError,
    add_user_queue_items,
    clear_user_queue,
    list_user_queue,
    remove_user_queue_item,
)

router = APIRouter(prefix="/queue", tags=["review queue"])


def _queue_response(items: list[RepostItem]) -> QueueResponse:
    response_items = [RepostResponse.model_validate(item) for item in items]
    return QueueResponse(items=response_items, total=len(response_items))


@router.get("", response_model=ApiResponse[QueueResponse])
def get_queue(
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(
        get_authenticated_session
    ),
) -> ApiResponse[QueueResponse]:
    _, user, _ = authenticated
    return ApiResponse(
        success=True,
        message="Review queue loaded",
        data=_queue_response(list_user_queue(db, user_id=user.id)),
    )


@router.post("", response_model=ApiResponse[QueueResponse])
def add_queue_items(
    payload: QueueAddRequest,
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(require_csrf),
) -> ApiResponse[QueueResponse]:
    _, user, _ = authenticated
    try:
        items = add_user_queue_items(
            db, user_id=user.id, repost_ids=payload.repost_ids
        )
    except QueueItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more library items were not found",
        ) from None
    return ApiResponse(
        success=True,
        message="Review queue updated",
        data=_queue_response(items),
    )


@router.delete("", response_model=ApiResponse[None])
def delete_queue(
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(require_csrf),
) -> ApiResponse[None]:
    _, user, _ = authenticated
    removed = clear_user_queue(db, user_id=user.id)
    return ApiResponse(
        success=True,
        message=f"Removed {removed} item(s) from your review queue",
        data=None,
    )


@router.delete("/{repost_id}", response_model=ApiResponse[None])
def delete_queue_item(
    repost_id: UUID,
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(require_csrf),
) -> ApiResponse[None]:
    _, user, _ = authenticated
    try:
        remove_user_queue_item(
            db, user_id=user.id, repost_id=repost_id
        )
    except QueueItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue item not found",
        ) from None
    return ApiResponse(
        success=True,
        message="Item removed from your review queue",
        data=None,
    )
