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
6. A redirect selects the URL by `short_code`, records one click event with the request IP, a simple User-Agent device category, and the optional `Referer` header, commits, and redirects to `original_url`.

## Analytics endpoints

All analytics endpoints require login and verify that the requested URL belongs to the logged-in user. The base endpoint and `/overview` return the same overview object:

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/urls/<id>/analytics` | Overview for one owned URL |
| GET | `/api/urls/<id>/analytics/overview` | Explicit overview endpoint |
| GET | `/api/urls/<id>/analytics/timeseries` | Daily click buckets; use `?granularity=hour` for hourly buckets |
| GET | `/api/urls/<id>/analytics/devices` | Counts by Desktop, Mobile, Tablet, or Unknown |
| GET | `/api/urls/<id>/analytics/referrers` | Counts by real referrer or Unknown |
| GET | `/api/urls/<id>/analytics/countries` | Real non-null country data only |
| GET | `/api/analytics/urls/top` | The logged-in user's URLs ranked by actual click count |

The overview contains `total_clicks`, `first_click`, `latest_click`, `most_common_device_type`, and `most_common_referrer`. Empty data is represented by `0`, `null`, or `[]` as appropriate; no values are fabricated. Raw IP addresses are stored privately but are never returned by analytics responses.

Country remains unavailable unless a real geolocation provider populates `clicks.country`. No provider is configured. CTR is not reported because the application does not record a meaningful impressions event.