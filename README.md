# Repost Cleaner API

## Repost library

All `/api/v1/reposts` endpoints require an authenticated session. The API derives
the owner from that session; clients must not send a `user_id`. Mutating requests
also require the CSRF token returned by the authentication flow and the request
headers used by the frontend client.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/reposts` | List the signed-in user's items. Supports `page`, `page_size` (maximum 100), `search`, `status` (`saved` or `archived`), and `sort` (`newest`, `oldest`, or `title`). |
| `GET` | `/api/v1/reposts/{repost_id}` | Get one item owned by the signed-in user. |
| `POST` | `/api/v1/reposts` | Add a user-managed item to the library. |
| `PATCH` | `/api/v1/reposts/{repost_id}` | Update an item's editable fields. |
| `DELETE` | `/api/v1/reposts/{repost_id}` | Delete the application's library record only. |

List responses contain `items`, `total`, `page`, `page_size`, and
`total_pages`. A record deletion does not remove a repost from TikTok. TikTok
integration and live account data are not available.

## Review queue

All `/api/v1/queue` endpoints require an authenticated session. Queue records are
owned by the authenticated user and can reference only that user's library
items. Mutations require the same trusted-origin and CSRF headers as repost
mutations. Adding an item already in the queue is idempotent.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/queue` | List the signed-in user's queued library items in queue order. |
| `POST` | `/api/v1/queue` | Add one or more owned items using `{"repost_ids": ["..."]}`; accepts 1–100 UUIDs. |
| `DELETE` | `/api/v1/queue/{repost_id}` | Remove one owned library item from the queue. |
| `DELETE` | `/api/v1/queue` | Clear the signed-in user's queue. |

Deleting a repost library item automatically removes its queue entry. Sample
preview queue operations remain client-only and are not written to user data.
Queue entries currently support list, add, remove, and clear only. Status and
priority updates are not implemented and do not produce activity events.

## Activity history

All `/api/v1/activities` endpoints require an authenticated session. Activity
records are created in the same transaction as successful library and queue
changes. They are scoped to the signed-in user and retained after the related
repost or queue entry is removed. Activity descriptions contain no account
credentials or session data.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/activities` | List the signed-in user's activity. Supports `page`, `page_size` (maximum 100), `type`, and `sort` (`newest` or `oldest`). |

Supported `type` values are `repost_created`, `repost_updated`,
`repost_deleted`, `queue_item_added`, and `queue_item_removed`. Responses
include `items`, `total`, `page`, `page_size`, and `total_pages`. Queue
preview/sample interactions are not persisted.
Queue status/priority activity types are not supported because the queue does
not yet expose those operations.

## User settings

All `/api/v1/users/me` endpoints require the authenticated session; mutation
requests also require the trusted-origin and CSRF headers. The API derives the
user from the session and does not accept a client-supplied user ID.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/auth/me` | Retrieve the current profile, including account creation date (existing authentication endpoint). |
| `PATCH` | `/api/v1/users/me` | Update the display name. Email changes are unavailable without verification support. |
| `GET` | `/api/v1/users/me/preferences` | Retrieve supported account preferences. |
| `PATCH` | `/api/v1/users/me/preferences` | Persist the compact library grid preference. |
| `POST` | `/api/v1/users/me/change-password` | Change password after verifying the current password; revokes other active sessions. |
| `DELETE` | `/api/v1/users/me` | Delete the account after password confirmation. This removes Repost Cleaner data only. |

Passwords are validated using the registration policy and hashed with the
existing Argon2id implementation. The current session remains active after a
password change; other active sessions are revoked. Theme switching,
notifications, username, and email changes are not currently supported.

## Database migration

After configuring the backend environment for the intended database, apply
migrations with:

```sh
alembic upgrade head
```

Revision `20261102_02` adds the repost library. Revision `20261103_03` adds
owner-scoped `queue_items` with cascade foreign keys and a composite primary
key. Revision `20261103_04` adds user-owned `activities` with no foreign key to
repost records, preserving history after item deletion. Revision `20261103_05`
adds the account-level compact library preference. Review the configured
database target before running migrations; do not use a production database for
local verification.

## Run locally

Activate the backend virtual environment, configure the required environment
variables, then start the API:

```sh
uvicorn app.main:app --reload
```
