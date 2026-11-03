from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import (
    SESSION_COOKIE_NAME,
    get_authenticated_session,
    require_csrf,
)
from app.db.session import get_db
from app.models.session import UserSession
from app.models.user import User
from app.schemas.auth import ApiResponse, UserResponse
from app.schemas.user import (
    PasswordChangeRequest,
    PasswordConfirmation,
    UserPreferencesResponse,
    UserPreferencesUpdate,
    UserProfileUpdate,
)
from app.services.user_settings_service import (
    InvalidCurrentPasswordError,
    change_user_password,
    delete_user_account,
    update_user_preferences,
    update_user_profile,
)

router = APIRouter(prefix="/users", tags=["user settings"])


@router.patch("/me", response_model=ApiResponse[UserResponse])
def patch_my_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(require_csrf),
) -> ApiResponse[UserResponse]:
    _, user, _ = authenticated
    updated = update_user_profile(
        db,
        user=user,
        display_name=payload.display_name,
    )
    return ApiResponse(
        success=True,
        message="Account profile updated",
        data=UserResponse.model_validate(updated),
    )


@router.get(
    "/me/preferences",
    response_model=ApiResponse[UserPreferencesResponse],
)
def get_my_preferences(
    authenticated: tuple[UserSession, User, str] = Depends(
        get_authenticated_session
    ),
) -> ApiResponse[UserPreferencesResponse]:
    _, user, _ = authenticated
    return ApiResponse(
        success=True,
        message="Workspace preferences loaded",
        data=UserPreferencesResponse(
            compact_library_grid=user.compact_library_grid
        ),
    )


@router.patch(
    "/me/preferences",
    response_model=ApiResponse[UserPreferencesResponse],
)
def patch_my_preferences(
    payload: UserPreferencesUpdate,
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(require_csrf),
) -> ApiResponse[UserPreferencesResponse]:
    _, user, _ = authenticated
    updated = update_user_preferences(
        db,
        user=user,
        compact_library_grid=payload.compact_library_grid,
    )
    return ApiResponse(
        success=True,
        message="Workspace preferences updated",
        data=UserPreferencesResponse(
            compact_library_grid=updated.compact_library_grid
        ),
    )


@router.post("/me/change-password", response_model=ApiResponse[None])
def post_change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(require_csrf),
) -> ApiResponse[None]:
    current_session, user, _ = authenticated
    try:
        change_user_password(
            db,
            user=user,
            current_session=current_session,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except InvalidCurrentPasswordError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        ) from None
    return ApiResponse(
        success=True,
        message="Password updated. Other active sessions were signed out.",
        data=None,
    )


@router.delete("/me", response_model=ApiResponse[None])
def delete_my_account(
    payload: PasswordConfirmation,
    response: Response,
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(require_csrf),
) -> ApiResponse[None]:
    _, user, _ = authenticated
    try:
        delete_user_account(
            db, user=user, current_password=payload.current_password
        )
    except InvalidCurrentPasswordError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        ) from None
    settings = get_settings()
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )
    return ApiResponse(
        success=True,
        message=(
            "Repost Cleaner account data deleted. "
            "No original content on TikTok was changed."
        ),
        data=None,
    )
