from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.session import UserSession
from app.models.user import User


def update_display_name(
    db: Session, *, user: User, display_name: str | None
) -> User:
    user.display_name = display_name
    db.commit()
    db.refresh(user)
    return user


def update_preferences(
    db: Session, *, user: User, compact_library_grid: bool
) -> User:
    user.compact_library_grid = compact_library_grid
    db.commit()
    db.refresh(user)
    return user


def revoke_other_sessions(
    db: Session,
    *,
    user_id: UUID,
    current_session_id: UUID,
    revoked_at: datetime,
) -> None:
    db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.id != current_session_id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=revoked_at)
    )


def delete_user(db: Session, *, user: User) -> None:
    db.delete(user)
    db.commit()
