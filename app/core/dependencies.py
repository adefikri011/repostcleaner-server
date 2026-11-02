from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.security import hash_session_token, verify_csrf_token
from app.db.session import get_db
from app.models.session import UserSession
from app.models.user import User

SESSION_COOKIE_NAME = "repost_session"


def require_trusted_browser_request(request: Request) -> None:
    settings = get_settings()
    origin = request.headers.get("origin")
    request_marker = request.headers.get("x-repost-request")
    if origin not in settings.frontend_origins or request_marker != "browser":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request origin could not be verified",
        )


def get_authenticated_session(
    request: Request,
    db: Session = Depends(get_db),
) -> tuple[UserSession, User, str]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    user_session = db.scalar(
        select(UserSession)
        .options(joinedload(UserSession.user))
        .where(UserSession.token_hash == hash_session_token(token))
    )
    now = datetime.now(UTC)
    if (
        user_session is None
        or user_session.revoked_at is not None
        or _as_utc(user_session.expires_at) <= now
        or not user_session.user.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user_session, user_session.user, token


def require_csrf(
    request: Request,
    authenticated: tuple[UserSession, User, str] = Depends(
        get_authenticated_session
    ),
) -> tuple[UserSession, User, str]:
    require_trusted_browser_request(request)
    csrf_token = request.headers.get("x-csrf-token", "")
    if not verify_csrf_token(authenticated[2], csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request could not be verified",
        )
    return authenticated


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
