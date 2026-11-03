from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.session import UserSession
from app.models.user import User
from app.repositories import user_settings_repository


class InvalidCurrentPasswordError(Exception):
    pass


def update_user_profile(
    db: Session, *, user: User, display_name: str | None
) -> User:
    return user_settings_repository.update_display_name(
        db, user=user, display_name=display_name
    )


def update_user_preferences(
    db: Session, *, user: User, compact_library_grid: bool
) -> User:
    return user_settings_repository.update_preferences(
        db, user=user, compact_library_grid=compact_library_grid
    )


def change_user_password(
    db: Session,
    *,
    user: User,
    current_session: UserSession,
    current_password: str,
    new_password: str,
) -> None:
    if not verify_password(user.password_hash, current_password):
        raise InvalidCurrentPasswordError
    user.password_hash = hash_password(new_password)
    user_settings_repository.revoke_other_sessions(
        db,
        user_id=user.id,
        current_session_id=current_session.id,
        revoked_at=datetime.now(UTC),
    )
    db.commit()


def delete_user_account(
    db: Session, *, user: User, current_password: str
) -> None:
    if not verify_password(user.password_hash, current_password):
        raise InvalidCurrentPasswordError
    user_settings_repository.delete_user(db, user=user)
