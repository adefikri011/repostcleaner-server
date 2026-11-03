from uuid import uuid4

from typing import Any

from fastapi.testclient import TestClient

ORIGIN_HEADERS = {
    "Origin": "http://localhost:5173",
    "X-Repost-Request": "browser",
}


def register_and_login(client: TestClient, email: str = "queue@example.com") -> str:
    registered = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN_HEADERS,
        json={"email": email, "password": "Secure-Password-123"},
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


def create_item(
    client: TestClient, csrf_token: str, **overrides: str
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/reposts",
        headers=mutation_headers(csrf_token),
        json={
            "source_platform": "example",
            "source_id": str(uuid4()),
            **overrides,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_queue_lists_adds_removes_and_clears_user_items(client) -> None:
    test_client, _ = client
    csrf_token = register_and_login(test_client)
    first = create_item(test_client, csrf_token, title="First queue item")
    second = create_item(test_client, csrf_token, title="Second queue item")

    empty = test_client.get("/api/v1/queue")
    assert empty.status_code == 200
    assert empty.json()["data"] == {"items": [], "total": 0}

    added = test_client.post(
        "/api/v1/queue",
        headers=mutation_headers(csrf_token),
        json={"repost_ids": [first["id"], second["id"], first["id"]]},
    )
    assert added.status_code == 200
    assert added.json()["data"]["total"] == 2
    assert {item["id"] for item in added.json()["data"]["items"]} == {
        first["id"],
        second["id"],
    }

    repeated = test_client.post(
        "/api/v1/queue",
        headers=mutation_headers(csrf_token),
        json={"repost_ids": [first["id"]]},
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"]["total"] == 2

    removed = test_client.delete(
        f"/api/v1/queue/{first['id']}",
        headers=mutation_headers(csrf_token),
    )
    assert removed.status_code == 200
    queue_items = test_client.get("/api/v1/queue").json()["data"]["items"]
    assert [item["id"] for item in queue_items] == [second["id"]]

    cleared = test_client.delete(
        "/api/v1/queue", headers=mutation_headers(csrf_token)
    )
    assert cleared.status_code == 200
    assert test_client.get("/api/v1/queue").json()["data"] == {
        "items": [],
        "total": 0,
    }


def test_queue_rejects_foreign_or_missing_reposts_atomically(client) -> None:
    test_client, _ = client
    first_csrf = register_and_login(test_client, email="queue-first@example.com")
    foreign_item = create_item(test_client, first_csrf, title="Private item")
    first_queue = test_client.post(
        "/api/v1/queue",
        headers=mutation_headers(first_csrf),
        json={"repost_ids": [foreign_item["id"]]},
    )
    assert first_queue.status_code == 200

    test_client.cookies.clear()
    second_csrf = register_and_login(test_client, email="queue-second@example.com")
    owned_item = create_item(test_client, second_csrf, title="Owned item")

    response = test_client.post(
        "/api/v1/queue",
        headers=mutation_headers(second_csrf),
        json={"repost_ids": [owned_item["id"], foreign_item["id"]]},
    )
    assert response.status_code == 404
    assert test_client.get("/api/v1/queue").json()["data"] == {
        "items": [],
        "total": 0,
    }
    assert test_client.delete(
        f"/api/v1/queue/{foreign_item['id']}",
        headers=mutation_headers(second_csrf),
    ).status_code == 404

    missing = test_client.post(
        "/api/v1/queue",
        headers=mutation_headers(second_csrf),
        json={"repost_ids": [str(uuid4())]},
    )
    assert missing.status_code == 404

    test_client.cookies.clear()
    test_client.post(
        "/api/v1/auth/login",
        headers=ORIGIN_HEADERS,
        json={
            "email": "queue-first@example.com",
            "password": "Secure-Password-123",
        },
    )
    first_queue_after_attack = test_client.get("/api/v1/queue").json()["data"]
    assert [item["id"] for item in first_queue_after_attack["items"]] == [
        foreign_item["id"]
    ]


def test_queue_endpoints_require_authentication_and_csrf(client) -> None:
    test_client, _ = client
    repost_id = uuid4()
    assert test_client.get("/api/v1/queue").status_code == 401
    assert test_client.post(
        "/api/v1/queue", json={"repost_ids": [str(repost_id)]}
    ).status_code == 401
    assert test_client.delete("/api/v1/queue").status_code == 401
    assert test_client.delete(f"/api/v1/queue/{repost_id}").status_code == 401

    csrf_token = register_and_login(test_client)
    bad_csrf = test_client.post(
        "/api/v1/queue",
        headers=ORIGIN_HEADERS,
        json={"repost_ids": [str(repost_id)]},
    )
    assert bad_csrf.status_code == 403
    assert test_client.delete(
        "/api/v1/queue", headers=ORIGIN_HEADERS
    ).status_code == 403
    assert csrf_token


def test_queue_rejects_invalid_payload_and_cascades_repost_deletion(client) -> None:
    test_client, _ = client
    csrf_token = register_and_login(test_client)
    item = create_item(test_client, csrf_token, title="Will be deleted")

    for payload in ({}, {"repost_ids": []}, {"repost_ids": ["not-a-uuid"]}):
        response = test_client.post(
            "/api/v1/queue",
            headers=mutation_headers(csrf_token),
            json=payload,
        )
        assert response.status_code == 422

    add = test_client.post(
        "/api/v1/queue",
        headers=mutation_headers(csrf_token),
        json={"repost_ids": [item["id"]]},
    )
    assert add.status_code == 200
    deleted = test_client.delete(
        f"/api/v1/reposts/{item['id']}",
        headers=mutation_headers(csrf_token),
    )
    assert deleted.status_code == 200
    assert test_client.get("/api/v1/queue").json()["data"] == {
        "items": [],
        "total": 0,
    }
