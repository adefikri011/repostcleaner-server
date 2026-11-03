from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.repost_item import RepostItem

ORIGIN_HEADERS = {
    "Origin": "http://localhost:5173",
    "X-Repost-Request": "browser",
}


def register_and_login(
    client: TestClient,
    *,
    email: str = "repost-user@example.com",
) -> str:
    registered = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN_HEADERS,
        json={
            "email": email,
            "password": "Secure-Password-123",
            "display_name": "Library User",
        },
    )
    assert registered.status_code == 201
    response = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN_HEADERS,
        json={"email": email, "password": "Secure-Password-123"},
    )
    assert response.status_code == 200
    return response.json()["data"]["csrf_token"]


def mutation_headers(csrf_token: str) -> dict[str, str]:
    return {**ORIGIN_HEADERS, "X-CSRF-Token": csrf_token}


def sample_payload(**overrides: object) -> dict[str, object]:
    return {
        "source_platform": "example",
        "source_id": str(uuid4()),
        "title": "A user-managed repost",
        "description": "A description for searching",
        "thumbnail_url": "https://example.test/image.jpg",
        "original_url": "https://example.test/item",
        "creator_username": "sample_creator",
        "creator_display_name": "Sample Creator",
        **overrides,
    }


def create_item(
    client: TestClient,
    csrf_token: str,
    **overrides: object,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/reposts",
        headers=mutation_headers(csrf_token),
        json=sample_payload(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_repost_crud_persists_owner_scoped_records(client) -> None:
    test_client, engine = client
    csrf_token = register_and_login(test_client)
    item = create_item(test_client, csrf_token)
    repost_id = item["id"]

    assert item["status"] == "saved"
    assert item["source_platform"] == "example"
    detail = test_client.get(f"/api/v1/reposts/{repost_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == repost_id

    updated = test_client.patch(
        f"/api/v1/reposts/{repost_id}",
        headers=mutation_headers(csrf_token),
        json={"title": "Updated title", "status": "archived"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "Updated title"
    assert updated.json()["data"]["status"] == "archived"

    deleted = test_client.delete(
        f"/api/v1/reposts/{repost_id}",
        headers=mutation_headers(csrf_token),
    )
    assert deleted.status_code == 200
    assert "does not remove a repost" in deleted.json()["message"]
    assert test_client.get(f"/api/v1/reposts/{repost_id}").status_code == 404

    with Session(engine) as db:
        assert db.scalar(select(RepostItem)) is None


def test_list_supports_pagination_and_stable_sorting(client) -> None:
    test_client, _ = client
    csrf_token = register_and_login(test_client)
    create_item(test_client, csrf_token, title="Charlie")
    create_item(test_client, csrf_token, title="Alpha")
    create_item(test_client, csrf_token, title="Bravo")

    response = test_client.get(
        "/api/v1/reposts?page=1&page_size=2&sort=title"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total_pages"] == 2
    assert [item["title"] for item in data["items"]] == ["Alpha", "Bravo"]

    last_page = test_client.get(
        "/api/v1/reposts?page=2&page_size=2&sort=title"
    ).json()["data"]
    assert [item["title"] for item in last_page["items"]] == ["Charlie"]


def test_list_search_and_status_filter_are_applied_together(client) -> None:
    test_client, _ = client
    csrf_token = register_and_login(test_client)
    create_item(
        test_client,
        csrf_token,
        title="Evening study",
        description="warm window light",
        status="archived",
    )
    create_item(test_client, csrf_token, title="Morning notes")

    response = test_client.get(
        "/api/v1/reposts?search=window&status=archived"
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["total"] == 1
    assert result["items"][0]["title"] == "Evening study"

    escaped_search = test_client.get("/api/v1/reposts?search=%25")
    assert escaped_search.json()["data"]["total"] == 0


def test_empty_library_has_zero_pages(client) -> None:
    test_client, _ = client
    register_and_login(test_client)

    response = test_client.get("/api/v1/reposts")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 24,
        "total_pages": 0,
    }


def test_every_repost_endpoint_requires_authentication(client) -> None:
    test_client, _ = client
    repost_id = uuid4()

    responses = [
        test_client.get("/api/v1/reposts"),
        test_client.get(f"/api/v1/reposts/{repost_id}"),
        test_client.post(
            "/api/v1/reposts",
            headers=ORIGIN_HEADERS,
            json=sample_payload(),
        ),
        test_client.patch(
            f"/api/v1/reposts/{repost_id}",
            headers=ORIGIN_HEADERS,
            json={"title": "Changed"},
        ),
        test_client.delete(
            f"/api/v1/reposts/{repost_id}",
            headers=ORIGIN_HEADERS,
        ),
    ]

    assert [response.status_code for response in responses] == [401] * 5


def test_user_cannot_read_update_or_delete_another_users_item(client) -> None:
    test_client, _ = client
    first_csrf = register_and_login(test_client, email="first@example.com")
    item = create_item(test_client, first_csrf, title="Private to first user")
    repost_id = item["id"]

    test_client.cookies.clear()
    second_csrf = register_and_login(test_client, email="second@example.com")

    second_user_library = test_client.get("/api/v1/reposts")
    assert second_user_library.status_code == 200
    assert second_user_library.json()["data"]["total"] == 0
    assert second_user_library.json()["data"]["items"] == []
    assert test_client.get(f"/api/v1/reposts/{repost_id}").status_code == 404
    update = test_client.patch(
        f"/api/v1/reposts/{repost_id}",
        headers=mutation_headers(second_csrf),
        json={"title": "Attempted cross-user edit"},
    )
    assert update.status_code == 404
    delete = test_client.delete(
        f"/api/v1/reposts/{repost_id}",
        headers=mutation_headers(second_csrf),
    )
    assert delete.status_code == 404

    test_client.cookies.clear()
    test_client.post(
        "/api/v1/auth/login",
        headers=ORIGIN_HEADERS,
        json={
            "email": "first@example.com",
            "password": "Secure-Password-123",
        },
    )
    assert test_client.get(f"/api/v1/reposts/{repost_id}").status_code == 200


def test_mutations_require_csrf_and_trusted_origin(client) -> None:
    test_client, _ = client
    csrf_token = register_and_login(test_client)
    item = create_item(test_client, csrf_token)

    no_csrf = test_client.patch(
        f"/api/v1/reposts/{item['id']}",
        headers=ORIGIN_HEADERS,
        json={"title": "No token"},
    )
    wrong_origin = test_client.delete(
        f"/api/v1/reposts/{item['id']}",
        headers={
            "Origin": "https://untrusted.example",
            "X-Repost-Request": "browser",
            "X-CSRF-Token": csrf_token,
        },
    )
    assert no_csrf.status_code == 403
    assert wrong_origin.status_code == 403


def test_invalid_payloads_are_rejected_without_database_changes(client) -> None:
    test_client, engine = client
    csrf_token = register_and_login(test_client)
    invalid_payloads = [
        {**sample_payload(), "user_id": str(uuid4())},
        {**sample_payload(), "source_platform": ""},
        {**sample_payload(), "thumbnail_url": "javascript:alert(1)"},
        {**sample_payload(), "status": "deleted"},
    ]

    for payload in invalid_payloads:
        response = test_client.post(
            "/api/v1/reposts",
            headers=mutation_headers(csrf_token),
            json=payload,
        )
        assert response.status_code == 422
        assert response.json()["message"] == "Invalid request data"

    empty_patch = test_client.patch(
        f"/api/v1/reposts/{uuid4()}",
        headers=mutation_headers(csrf_token),
        json={},
    )
    assert empty_patch.status_code == 422
    with Session(engine) as db:
        assert db.scalar(select(RepostItem)) is None


def test_source_id_is_unique_per_owner_and_platform(client) -> None:
    test_client, _ = client
    csrf_token = register_and_login(test_client)
    payload = sample_payload(source_id="source-123")
    first = test_client.post(
        "/api/v1/reposts",
        headers=mutation_headers(csrf_token),
        json=payload,
    )
    duplicate = test_client.post(
        "/api/v1/reposts",
        headers=mutation_headers(csrf_token),
        json=payload,
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["data"] is None
