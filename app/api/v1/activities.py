from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_authenticated_session
from app.db.session import get_db
from app.models.session import UserSession
from app.models.user import User
from app.schemas.activity import ActivityList, ActivityType
from app.schemas.auth import ApiResponse
from app.services.activity_service import list_user_activities

router = APIRouter(prefix="/activities", tags=["activity history"])


@router.get("", response_model=ApiResponse[ActivityList])
def get_activities(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    activity_type: ActivityType | None = Query(default=None, alias="type"),
    sort: Literal["newest", "oldest"] = "newest",
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(
        get_authenticated_session
    ),
) -> ApiResponse[ActivityList]:
    _, user, _ = authenticated
    data = list_user_activities(
        db,
        user_id=user.id,
        page=page,
        page_size=page_size,
        activity_type=activity_type,
        sort=sort,
    )
    return ApiResponse(success=True, message="Activity history loaded", data=data)
