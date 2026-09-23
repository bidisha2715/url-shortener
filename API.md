# API

The PostgreSQL URL API is exposed by the Flask application factory. The legacy SQLite routes remain in `run.py` until the replacement has been manually verified.

## Authentication

All URL endpoints require the Flask session created by `POST /api/auth/register` or `POST /api/auth/login`.

| Method | Path | Success |
|---|---|---|
| POST | `/api/auth/register` | `201` |
| POST | `/api/auth/login` | `200` |
| POST | `/api/auth/logout` | `200` |

## URL endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/urls` | Create a generated or custom short URL |
| GET | `/api/urls` | List only the logged-in user's URLs |
| GET | `/api/urls/<id>` | Retrieve one owned URL |
| PUT | `/api/urls/<id>` | Change the destination or custom alias |
| DELETE | `/api/urls/<id>` | Delete one owned URL |
| GET | `/<short_code>` | Record a click and redirect |

Creation and update use JSON. A creation body looks like:

```json
{
  "original_url": "https://example.com/docs",
  "custom_alias": "docs"
}
```

`custom_alias` is optional and accepts 3-50 letters, numbers, `_`, or `-`. A duplicate alias returns `409`. Invalid input returns `400`, missing login returns `401`, another user's URL returns `403`, and a missing URL returns `404`.

## URL flow

1. The client sends JSON to Flask.
2. Flask validates the URL and reads the authenticated user ID from the session.
3. The URL row is inserted into PostgreSQL with that user ID.
4. Generated codes use six cryptographically secure letters/numbers. The unique database constraint is authoritative; a generated-code conflict rolls back the insert and retries up to ten times.
5. A custom alias becomes both `short_code` and `custom_alias`, so the database prevents collisions.
6. A redirect selects the URL by `short_code`, inserts one row into `clicks`, commits, and redirects to `original_url`.

No country, device, referrer, or CTR data is collected in this stage.