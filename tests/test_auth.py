from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, hash_session_token
from app.models.login_attempt import LoginAttempt
from app.models.session import UserSession
from app.models.user import User

ORIGIN_HEADERS = {
    "Origin": "http://localhost:5173",
    "X-Repost-Request": "browser",
}


def register_account(
    client: TestClient,
    *,
    email: str = "person@example.com",
    password: str = "A-secure-Password-123",
    display_name: str | None = "Workspace User",
) -> Any:
    return client.post(
        "/api/v1/auth/register",
        headers=ORIGIN_HEADERS,
        json={
            "email": email,
            "password": password,
            "display_name": display_name,
        },
    )


def login_account(
    client: TestClient,
    *,
    email: str = "person@example.com",
    password: str = "A-secure-Password-123",
) -> Any:
    return client.post(
        "/api/v1/auth/login",
        headers=ORIGIN_HEADERS,
        json={"email": email, "password": password},
    )


def test_registration_creates_hashed_user_without_session(client) -> None:
    test_client, engine = client
    response = register_account(test_client)

    assert response.status_code == 201
    assert response.json()["success"] is True
    assert response.json()["data"]["user"]["email"] == "person@example.com"
    assert "password_hash" not in response.json()["data"]["user"]
    assert "set-cookie" not in response.headers

    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == "person@example.com"))
        assert user is not None
        assert user.password_hash.startswith("$argon2id$")
        assert user.password_hash != "A-secure-Password-123"


def test_registration_rejects_duplicate_email_case_insensitively(client) -> None:
    test_client, _ = client
    assert register_account(test_client).status_code == 201

    duplicate = register_account(test_client, email="PERSON@example.com")

    assert duplicate.status_code == 409
    assert duplicate.json()["data"] is None


def test_registration_rejects_invalid_email_and_weak_password(client) -> None:
    test_client, _ = client
    invalid_email = register_account(test_client, email="not-an-email")
    weak_password = register_account(
        test_client,
        email="another@example.com",
        password="password",
    )

    assert invalid_email.status_code == 422
    assert invalid_email.json() == {
        "success": False,
        "message": "Invalid request data",
        "data": None,
    }
    assert weak_password.status_code == 422


def test_login_sets_http_only_cookie_and_me_returns_user(client) -> None:
    test_client, engine = client
    register_account(test_client)

    response = login_account(test_client)

    assert response.status_code == 200
    assert response.json()["message"] == "Login successful"
    assert response.json()["data"]["csrf_token"]
    assert "repost_session=" in response.headers["set-cookie"]
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    assert "secure" not in response.headers["set-cookie"].lower()
    assert response.json()["data"]["user"]["email"] == "person@example.com"
    assert response.cookies.get("repost_session") not in response.text

    with Session(engine) as db:
        user_session = db.scalar(select(UserSession))
        assert user_session is not None
        assert user_session.token_hash != test_client.cookies.get("repost_session")

    current = test_client.get("/api/v1/auth/me")
    assert current.status_code == 200
    assert current.json()["data"]["user"]["email"] == "person@example.com"
    assert current.json()["data"]["csrf_token"] == response.json()["data"]["csrf_token"]


def test_login_rejects_wrong_password_and_rate_limits_retries(client) -> None:
    test_client, engine = client
    register_account(test_client)

    for _ in range(5):
        response = login_account(test_client, password="Wrong-password-123")
        assert response.status_code == 401
        assert response.json()["message"] == "Invalid email or password"

    blocked = login_account(test_client)
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "900"

    with Session(engine) as db:
        attempt = db.scalar(select(LoginAttempt))
        assert attempt is not None
        assert attempt.attempts == 5


def test_me_requires_valid_non_expired_and_unrevoked_session(client) -> None:
    test_client, engine = client
    register_account(test_client)
    assert test_client.get("/api/v1/auth/me").status_code == 401

    login_account(test_client)
    with Session(engine) as db:
        user_session = db.scalar(select(UserSession))
        assert user_session is not None
        user_session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    assert test_client.get("/api/v1/auth/me").status_code == 401

    test_client.cookies.clear()
    login_account(test_client)
    session_token = test_client.cookies.get("repost_session")
    assert session_token is not None
    with Session(engine) as db:
        user_session = db.scalar(
            select(UserSession).where(
                UserSession.token_hash == hash_session_token(session_token)
            )
        )
        assert user_session is not None
        user_session.revoked_at = datetime.now(UTC)
        db.commit()
    assert test_client.get("/api/v1/auth/me").status_code == 401


def test_logout_requires_csrf_revokes_session_and_clears_cookie(client) -> None:
    test_client, engine = client
    register_account(test_client)
    login_response = login_account(test_client)
    csrf_token = login_response.json()["data"]["csrf_token"]

    rejected = test_client.post("/api/v1/auth/logout", headers=ORIGIN_HEADERS)
    assert rejected.status_code == 403

    logged_out = test_client.post(
        "/api/v1/auth/logout",
        headers={**ORIGIN_HEADERS, "X-CSRF-Token": csrf_token},
    )
    assert logged_out.status_code == 200
    assert logged_out.json() == {
        "success": True,
        "message": "Logout successful",
        "data": None,
    }
    assert "repost_session=" in logged_out.headers["set-cookie"]
    assert test_client.get("/api/v1/auth/me").status_code == 401

    with Session(engine) as db:
        user_session = db.scalar(select(UserSession))
        assert user_session is not None
        assert user_session.revoked_at is not None


def test_mutating_auth_requests_require_trusted_origin(client) -> None:
    test_client, _ = client

    response = test_client.post(
        "/api/v1/auth/register",
        json={
            "email": "person@example.com",
            "password": "A-secure-Password-123",
        },
    )

    assert response.status_code == 403
    assert response.json()["data"] is None


def test_authenticated_sessions_are_scoped_to_the_logged_in_user(client) -> None:
    test_client, _ = client
    register_account(test_client)
    register_account(
        test_client,
        email="second@example.com",
        display_name="Second User",
    )

    login_account(test_client)
    first_user = test_client.get("/api/v1/auth/me").json()["data"]["user"]
    login_account(test_client, email="second@example.com")
    second_user = test_client.get("/api/v1/auth/me").json()["data"]["user"]

    assert first_user["id"] != second_user["id"]
    assert second_user["email"] == "second@example.com"


def test_login_without_matching_user_uses_generic_error(client) -> None:
    test_client, _ = client

    response = login_account(test_client, email="missing@example.com")

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid email or password"
    assert "user" not in response.text.lower()
