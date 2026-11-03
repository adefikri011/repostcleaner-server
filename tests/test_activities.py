from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.activity import Activity

ORIGIN_HEADERS = {
    "Origin": "http://localhost:5173",
    "X-Repost-Request": "browser",
}


def register_and_login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN_HEADERS,
        json={"email": email, "password": "Secure-Password-123"},
    )
    assert response.status_code == 201
    response = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN_HEADERS,
        json={"email": email, "password": "Secure-Password-123"},
    )
    assert response.status_code == 200
    return response.json()["data"]["csrf_token"]


def mutation_headers(csrf_token: str) -> dict[str, str]:
    return {**ORIGIN_HEADERS, "X-CSRF-Token": csrf_token}


def create_repost(
    client: TestClient, csrf_token: str, title: str = "Activity item"
) -> dict:
    response = client.post(
        "/api/v1/reposts",
        headers=mutation_headers(csrf_token),
        json={
            "source_platform": "example",
            "source_id": str(uuid4()),
            "title": title,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def activity_types(client: TestClient) -> list[str]:
    response = client.get("/api/v1/activities")
    assert response.status_code == 200
    return [item["activity_type"] for item in response.json()["data"]["items"]]


def test_repost_successes_are_recorded_and_survive_entity_deletion(client) -> None:
    test_client, _ = client
    csrf_token = register_and_login(test_client, "activity-reposts@example.com")
    item = create_repost(test_client, csrf_token)
    assert activity_types(test_client) == ["repost_created"]

    updated = test_client.patch(
        f"/api/v1/reposts/{item['id']}",
        headers=mutation_headers(csrf_token),
        json={"title": "Changed title"},
    )
    assert updated.status_code == 200
    assert sorted(activity_types(test_client)) == sorted(
        ["repost_updated", "repost_created"]
    )

    deleted = test_client.delete(
        f"/api/v1/reposts/{item['id']}",
        headers=mutation_headers(csrf_token),
    )
    assert deleted.status_code == 200
    history = test_client.get("/api/v1/activities").json()["data"]
    assert sorted(entry["activity_type"] for entry in history["items"]) == sorted(
        ["repost_deleted", "repost_updated", "repost_created"]
    )
    assert all(entry["entity_id"] == item["id"] for entry in history["items"])


def test_queue_successes_are_recorded_only_when_queue_changes(client) -> None:
    test_client, _ = client
    csrf_token = register_and_login(test_client, "activity-queue@example.com")
    item = create_repost(test_client, csrf_token)

    headers = mutation_headers(csrf_token)
    added = test_client.post(
        "/api/v1/queue",
        headers=headers,
        json={"repost_ids": [item["id"]]},
    )
    assert added.status_code == 200
    assert sorted(activity_types(test_client)) == sorted(
        ["queue_item_added", "repost_created"]
    )

    duplicate = test_client.post(
        "/api/v1/queue",
        headers=headers,
        json={"repost_ids": [item["id"]]},
    )
    assert duplicate.status_code == 200
    assert sorted(activity_types(test_client)) == sorted(
        ["queue_item_added", "repost_created"]
    )

    removed = test_client.delete(
        f"/api/v1/queue/{item['id']}", headers=headers
    )
    assert removed.status_code == 200
    assert sorted(activity_types(test_client)) == sorted(
        ["queue_item_removed", "queue_item_added", "repost_created"]
    )


def test_failed_operations_do_not_create_success_activity(client) -> None:
    test_client, _ = client
    csrf_token = register_and_login(test_client, "activity-failures@example.com")
    headers = mutation_headers(csrf_token)
    invalid_create = test_client.post(
        "/api/v1/reposts",
        headers=headers,
        json={"source_platform": ""},
    )
    assert invalid_create.status_code == 422
    assert activity_types(test_client) == []

    missing_repost_id = str(uuid4())
    failed_update = test_client.patch(
        f"/api/v1/reposts/{missing_repost_id}",
        headers=headers,
        json={"title": "Missing"},
    )
    assert failed_update.status_code == 404
    failed_queue_add = test_client.post(
        "/api/v1/queue",
        headers=headers,
        json={"repost_ids": [missing_repost_id]},
    )
    assert failed_queue_add.status_code == 404
    failed_queue_remove = test_client.delete(
        f"/api/v1/queue/{missing_repost_id}", headers=headers
    )
    assert failed_queue_remove.status_code == 404
    assert activity_types(test_client) == []


def test_activity_history_is_private_authenticated_and_filterable(client) -> None:
    test_client, _ = client
    first_csrf = register_and_login(test_client, "activity-first@example.com")
    first_item = create_repost(test_client, first_csrf, "First user's item")
    test_client.patch(
        f"/api/v1/reposts/{first_item['id']}",
        headers=mutation_headers(first_csrf),
        json={"title": "Updated by first user"},
    )
    first_history = test_client.get("/api/v1/activities").json()["data"]
    assert first_history["total"] == 2
    assert first_history["total_pages"] == 1

    test_client.cookies.clear()
    second_csrf = register_and_login(test_client, "activity-second@example.com")
    second_item = create_repost(test_client, second_csrf, "Second user's item")
    second_history = test_client.get("/api/v1/activities").json()["data"]
    assert second_history["total"] == 1
    assert second_history["items"][0]["entity_id"] == second_item["id"]

    filtered = test_client.get("/api/v1/activities?type=repost_created")
    assert filtered.status_code == 200
    assert filtered.json()["data"]["total"] == 1
    assert filtered.json()["data"]["items"][0]["entity_id"] == second_item["id"]
    assert test_client.get("/api/v1/activities?type=unknown").status_code == 422

    test_client.cookies.clear()
    assert test_client.get("/api/v1/activities").status_code == 401


def test_activity_pagination_and_oldest_sort(client) -> None:
    test_client, engine = client
    csrf_token = register_and_login(test_client, "activity-pages@example.com")
    first = create_repost(test_client, csrf_token, "First item")
    second = create_repost(test_client, csrf_token, "Second item")
    third = create_repost(test_client, csrf_token, "Third item")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with Session(engine) as db:
        for offset, item in enumerate((first, second, third)):
            db.execute(
                update(Activity)
                .where(Activity.entity_id == UUID(item["id"]))
                .values(created_at=start + timedelta(minutes=offset))
            )
        db.commit()

    first_page = test_client.get(
        "/api/v1/activities?page=1&page_size=2&sort=oldest"
    ).json()["data"]
    assert first_page["total"] == 3
    assert first_page["page"] == 1
    assert first_page["page_size"] == 2
    assert first_page["total_pages"] == 2
    assert [row["entity_id"] for row in first_page["items"]] == [
        first["id"],
        second["id"],
    ]
    second_page = test_client.get(
        "/api/v1/activities?page=2&page_size=2&sort=oldest"
    ).json()["data"]
    assert [row["entity_id"] for row in second_page["items"]] == [third["id"]]


def test_clear_queue_records_each_removed_item(client) -> None:
    test_client, _ = client
    csrf_token = register_and_login(test_client, "activity-clear@example.com")
    first = create_repost(test_client, csrf_token, "First queue item")
    second = create_repost(test_client, csrf_token, "Second queue item")
    added = test_client.post(
        "/api/v1/queue",
        headers=mutation_headers(csrf_token),
        json={"repost_ids": [first["id"], second["id"]]},
    )
    assert added.status_code == 200

    cleared = test_client.delete(
        "/api/v1/queue", headers=mutation_headers(csrf_token)
    )
    assert cleared.status_code == 200
    result = test_client.get(
        "/api/v1/activities?type=queue_item_removed"
    ).json()["data"]
    assert result["total"] == 2
    assert {row["entity_id"] for row in result["items"]} == {
        first["id"],
        second["id"],
    }
