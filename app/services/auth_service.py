from datetime import UTC, datetime, timedelta

from sqlalchemy import case, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.security import (
    create_session_token,
    hash_login_fingerprint,
    hash_password,
    hash_session_token,
    password_hasher,
    verify_password,
)
from app.models.login_attempt import LoginAttempt
from app.models.session import UserSession
from app.models.user import User
from app.repositories.user_repository import create_user, get_user_by_email

LOGIN_FAILURE_LIMIT = 5
LOGIN_WINDOW = timedelta(minutes=15)
LOGIN_BLOCK_DURATION = timedelta(minutes=15)

_DUMMY_PASSWORD_HASH = password_hasher.hash("not-a-real-user-password")


class DuplicateEmailError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class LoginBlockedError(Exception):
    pass


def register_user(
    db: Session,
    *,
    email: str,
    display_name: str | None,
    password: str,
) -> User:
    if get_user_by_email(db, email) is not None:
        raise DuplicateEmailError
    password_hash = hash_password(password)
    return create_user(
        db,
        email=email,
        display_name=display_name,
        password_hash=password_hash,
    )


def authenticate_user(
    db: Session,
    *,
    email: str,
    password: str,
    client_host: str,
) -> tuple[User, str]:
    fingerprint = hash_login_fingerprint(email, client_host)
    attempt = db.scalar(
        select(LoginAttempt).where(LoginAttempt.fingerprint_hash == fingerprint)
    )
    now = datetime.now(UTC)
    if attempt is not None and attempt.blocked_until is not None:
        if _as_utc(attempt.blocked_until) > now:
            raise LoginBlockedError

    user = get_user_by_email(db, email)
    password_matches = verify_password(
        user.password_hash if user is not None else _DUMMY_PASSWORD_HASH,
        password,
    )
    if user is None or not user.is_active or not password_matches:
        _record_failed_login(db, fingerprint, now)
        raise InvalidCredentialsError

    db.query(LoginAttempt).filter(
        LoginAttempt.fingerprint_hash == fingerprint
    ).delete(synchronize_session=False)
    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    raw_token = create_session_token()
    expires_at = now + timedelta(hours=get_settings().session_expire_hours)
    user_session = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        expires_at=expires_at,
        last_active_at=now,
    )
    db.add(user_session)
    db.commit()
    return user, raw_token


def load_session(db: Session, token: str) -> tuple[UserSession, User] | None:
    user_session = db.scalar(
        select(UserSession)
        .options(joinedload(UserSession.user))
        .where(UserSession.token_hash == hash_session_token(token))
    )
    if (
        user_session is None
        or user_session.revoked_at is not None
        or _as_utc(user_session.expires_at) <= datetime.now(UTC)
        or not user_session.user.is_active
    ):
        return None
    return user_session, user_session.user


def revoke_session(db: Session, token: str) -> None:
    user_session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == hash_session_token(token)
        )
    )
    if user_session is not None and user_session.revoked_at is None:
        user_session.revoked_at = datetime.now(UTC)
        db.commit()


def update_last_active(db: Session, user_session: UserSession) -> None:
    user_session.last_active_at = datetime.now(UTC)
    db.commit()


def _record_failed_login(db: Session, fingerprint: str, now: datetime) -> None:
    table = LoginAttempt.__table__
    insert = (
        postgresql_insert(LoginAttempt)
        if db.bind is not None and db.bind.dialect.name == "postgresql"
        else sqlite_insert(LoginAttempt)
    )
    reset_window = table.c.window_started_at <= now - LOGIN_WINDOW
    next_attempts = case(
        (reset_window, 1),
        else_=table.c.attempts + 1,
    )
    statement = insert.values(
        fingerprint_hash=fingerprint,
        attempts=1,
        window_started_at=now,
        blocked_until=None,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.fingerprint_hash],
        set_={
            "attempts": next_attempts,
            "window_started_at": case(
                (reset_window, now),
                else_=table.c.window_started_at,
            ),
            "blocked_until": case(
                (reset_window, None),
                (next_attempts >= LOGIN_FAILURE_LIMIT, now + LOGIN_BLOCK_DURATION),
                else_=table.c.blocked_until,
            ),
        },
    )
    db.execute(statement)
    db.commit()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
