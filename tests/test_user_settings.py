from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.queue_item import QueueItem
from app.models.repost_item import RepostItem
from app.models.session import UserSession
from app.models.user import User

ORIGIN_HEADERS = {
    "Origin": "http://localhost:5173",
    "X-Repost-Request": "browser",
}


def register_and_login(
    client: TestClient, email: str
) -> tuple[str, str]:
    registered = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN_HEADERS,
        json={
            "email": email,
            "display_name": "Settings User",
            "password": "Secure-Password-123",
        },
    )
    assert registered.status_code == 201
    response = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN_HEADERS,
        json={"email": email, "password": "Secure-Password-123"},
    )
    assert response.status_code == 200
    return response.json()["data"]["csrf_token"], client.cookies.get(
        "repost_session"
    )


def mutation_headers(csrf_token: str) -> dict[str, str]:
    return {**ORIGIN_HEADERS, "X-CSRF-Token": csrf_token}


def test_profile_can_be_retrieved_updated_and_cleared(client) -> None:
    test_client, _ = client
    csrf_token, _ = register_and_login(test_client, "settings-profile@example.com")

    profile = test_client.get("/api/v1/auth/me")
    assert profile.status_code == 200
    profile_user = profile.json()["data"]["user"]
    assert profile_user["email"] == "settings-profile@example.com"
    assert profile_user["display_name"] == "Settings User"
    assert profile_user["created_at"]
    assert "password_hash" not in profile_user

    updated = test_client.patch(
        "/api/v1/users/me",
        headers=mutation_headers(csrf_token),
        json={"display_name": "  Updated Name  "},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["display_name"] == "Updated Name"

    cleared = test_client.patch(
        "/api/v1/users/me",
        headers=mutation_headers(csrf_token),
        json={"display_name": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["data"]["display_name"] is None


def test_profile_rejects_invalid_or_unsupported_fields(client) -> None:
    test_client, _ = client
    csrf_token, _ = register_and_login(test_client, "settings-invalid@example.com")
    headers = mutation_headers(csrf_token)

    assert test_client.patch(
        "/api/v1/users/me", headers=headers, json={}
    ).status_code == 422
    assert test_client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"display_name": "x" * 81},
    ).status_code == 422
    assert test_client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"email": "new@example.com"},
    ).status_code == 422
    assert test_client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"username": "not-supported"},
    ).status_code == 422


def test_user_settings_are_authenticated_and_isolated(client) -> None:
    test_client, _ = client
    assert test_client.get("/api/v1/auth/me").status_code == 401
    assert test_client.get("/api/v1/users/me/preferences").status_code == 401
    assert test_client.patch(
        "/api/v1/users/me/preferences",
        json={"compact_library_grid": True},
    ).status_code == 401

    first_csrf, _ = register_and_login(test_client, "settings-first@example.com")
    first_pref = test_client.patch(
        "/api/v1/users/me/preferences",
        headers=mutation_headers(first_csrf),
        json={"compact_library_grid": True},
    )
    assert first_pref.status_code == 200

    test_client.cookies.clear()
    register_and_login(test_client, "settings-second@example.com")
    second_pref = test_client.get("/api/v1/users/me/preferences")
    assert second_pref.status_code == 200
    assert second_pref.json()["data"]["compact_library_grid"] is False


def test_preferences_persist_and_validate_payload(client) -> None:
    test_client, _ = client
    csrf_token, _ = register_and_login(test_client, "settings-pref@example.com")
    headers = mutation_headers(csrf_token)

    initial = test_client.get("/api/v1/users/me/preferences")
    assert initial.json()["data"] == {"compact_library_grid": False}
    updated = test_client.patch(
        "/api/v1/users/me/preferences",
        headers=headers,
        json={"compact_library_grid": True},
    )
    assert updated.status_code == 200
    assert test_client.get("/api/v1/users/me/preferences").json()["data"] == {
        "compact_library_grid": True
    }
    assert test_client.patch(
        "/api/v1/users/me/preferences",
        headers=headers,
        json={"compact_library_grid": "not-a-boolean"},
    ).status_code == 422
    assert test_client.patch(
        "/api/v1/users/me/preferences",
        headers=headers,
        json={"compact_library_grid": True, "unknown": True},
    ).status_code == 422


def test_password_change_requires_current_password_and_revokes_other_sessions(
    client,
) -> None:
    test_client, engine = client
    email = "settings-password@example.com"
    csrf_token, first_session_token = register_and_login(test_client, email)
    test_client.cookies.clear()
    second_login = test_client.post(
        "/api/v1/auth/login",
        headers=ORIGIN_HEADERS,
        json={"email": email, "password": "Secure-Password-123"},
    )
    assert second_login.status_code == 200
    second_csrf = second_login.json()["data"]["csrf_token"]
    second_session_token = test_client.cookies.get("repost_session")
    assert first_session_token != second_session_token

    headers = mutation_headers(second_csrf)
    invalid_current = test_client.post(
        "/api/v1/users/me/change-password",
        headers=headers,
        json={
            "current_password": "incorrect",
            "new_password": "New-Strong-Password-456",
        },
    )
    assert invalid_current.status_code == 400
    invalid_new = test_client.post(
        "/api/v1/users/me/change-password",
        headers=headers,
        json={
            "current_password": "Secure-Password-123",
            "new_password": "weak",
        },
    )
    assert invalid_new.status_code == 422

    changed = test_client.post(
        "/api/v1/users/me/change-password",
        headers=headers,
        json={
            "current_password": "Secure-Password-123",
            "new_password": "New-Strong-Password-456",
        },
    )
    assert changed.status_code == 200
    assert test_client.get("/api/v1/auth/me").status_code == 200
    with Session(engine) as db:
        sessions = list(db.scalars(select(UserSession)))
        assert sum(session.revoked_at is not None for session in sessions) == 1

    test_client.cookies.clear()
    test_client.cookies.set("repost_session", first_session_token)
    assert test_client.get("/api/v1/auth/me").status_code == 401

    test_client.cookies.clear()
    new_login = test_client.post(
        "/api/v1/auth/login",
        headers=ORIGIN_HEADERS,
        json={"email": email, "password": "New-Strong-Password-456"},
    )
    assert new_login.status_code == 200
    assert "password_hash" not in new_login.json()["data"]["user"]


def test_account_deletion_requires_password_and_cascades_account_data(client) -> None:
    test_client, engine = client
    csrf_token, _ = register_and_login(test_client, "settings-delete@example.com")
    headers = mutation_headers(csrf_token)
    created = test_client.post(
        "/api/v1/reposts",
        headers=headers,
        json={
            "source_platform": "example",
            "source_id": str(uuid4()),
            "title": "Account removal fixture",
        },
    )
    assert created.status_code == 201
    repost_id = created.json()["data"]["id"]
    test_client.post(
        "/api/v1/queue",
        headers=headers,
        json={"repost_ids": [repost_id]},
    )

    rejected = test_client.request(
        "DELETE",
        "/api/v1/users/me",
        headers=headers,
        json={"current_password": "incorrect"},
    )
    assert rejected.status_code == 400
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1

    deleted = test_client.request(
        "DELETE",
        "/api/v1/users/me",
        headers=headers,
        json={"current_password": "Secure-Password-123"},
    )
    assert deleted.status_code == 200
    assert "No original content on TikTok was changed" in deleted.json()["message"]
    assert test_client.get("/api/v1/auth/me").status_code == 401
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0
        assert db.scalar(select(func.count()).select_from(UserSession)) == 0
        assert db.scalar(select(func.count()).select_from(RepostItem)) == 0
        assert db.scalar(select(func.count()).select_from(QueueItem)) == 0
        assert db.scalar(select(func.count()).select_from(Activity)) == 0
