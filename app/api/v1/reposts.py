from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_authenticated_session, require_csrf
from app.db.session import get_db
from app.models.session import UserSession
from app.models.user import User
from app.schemas.auth import ApiResponse
from app.schemas.repost import (
    RepostCreate,
    RepostList,
    RepostResponse,
    RepostStatus,
    RepostUpdate,
)
from app.services.repost_service import (
    RepostNotFoundError,
    create_user_repost,
    delete_user_repost,
    get_user_repost,
    list_user_reposts,
    update_user_repost,
)

router = APIRouter(prefix="/reposts", tags=["reposts"])


@router.get("", response_model=ApiResponse[RepostList])
def list_reposts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    repost_status: RepostStatus | None = Query(default=None, alias="status"),
    sort: Literal["newest", "oldest", "title"] = "newest",
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(
        get_authenticated_session
    ),
) -> ApiResponse[RepostList]:
    _, user, _ = authenticated
    data = list_user_reposts(
        db,
        user_id=user.id,
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        status=repost_status,
        sort=sort,
    )
    return ApiResponse(success=True, message="Reposts loaded", data=data)


@router.post(
    "",
    response_model=ApiResponse[RepostResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_repost(
    payload: RepostCreate,
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(require_csrf),
) -> ApiResponse[RepostResponse]:
    _, user, _ = authenticated
    try:
        repost = create_user_repost(db, user_id=user.id, payload=payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This source item is already in your library",
        ) from None
    return ApiResponse(
        success=True,
        message="Item added to your Repost Cleaner library",
        data=RepostResponse.model_validate(repost),
    )


@router.get("/{repost_id}", response_model=ApiResponse[RepostResponse])
def get_repost(
    repost_id: UUID,
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(
        get_authenticated_session
    ),
) -> ApiResponse[RepostResponse]:
    _, user, _ = authenticated
    try:
        repost = get_user_repost(db, user_id=user.id, repost_id=repost_id)
    except RepostNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repost item not found",
        ) from None
    return ApiResponse(
        success=True,
        message="Repost item loaded",
        data=RepostResponse.model_validate(repost),
    )


@router.patch("/{repost_id}", response_model=ApiResponse[RepostResponse])
def patch_repost(
    repost_id: UUID,
    payload: RepostUpdate,
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(require_csrf),
) -> ApiResponse[RepostResponse]:
    _, user, _ = authenticated
    try:
        repost = update_user_repost(
            db, user_id=user.id, repost_id=repost_id, payload=payload
        )
    except RepostNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repost item not found",
        ) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This source item is already in your library",
        ) from None
    return ApiResponse(
        success=True,
        message="Repost item updated",
        data=RepostResponse.model_validate(repost),
    )


@router.delete("/{repost_id}", response_model=ApiResponse[None])
def delete_repost(
    repost_id: UUID,
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(require_csrf),
) -> ApiResponse[None]:
    _, user, _ = authenticated
    try:
        delete_user_repost(db, user_id=user.id, repost_id=repost_id)
    except RepostNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repost item not found",
        ) from None
    return ApiResponse(
        success=True,
        message=(
            "Item removed from your application library. "
            "This does not remove a repost from its source platform."
        ),
        data=None,
    )
