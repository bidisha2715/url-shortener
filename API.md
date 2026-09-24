# API

The PostgreSQL URL API is exposed by the modern Flask application factory (`app:create_app()`). The legacy SQLite routes in `run.py` are preserved solely as legacy reference.

## Authentication

All private URL and analytics endpoints require the signed Flask session created by `POST /api/auth/register` or `POST /api/auth/login`.

| Method | Path | Success | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | `201` | Create a new user account and initiate session |
| POST | `/api/auth/login` | `200` | Authenticate existing user credentials |
| POST | `/api/auth/logout` | `200` | Terminate session |

## URL & Redirection Endpoints

| Method | Path | Success | Purpose |
|---|---|---|---|
| POST | `/api/urls` | `201` | Create a short URL with generated code or custom alias |
| GET | `/api/urls` | `200` | List all URLs owned by the authenticated user |
| GET | `/api/urls/<id>` | `200` | Retrieve details for one owned URL |
| PUT | `/api/urls/<id>` | `200` | Update destination URL or custom alias |
| DELETE | `/api/urls/<id>` | `200` | Delete an owned URL and associated event records |
| GET | `/<short_code>` | `302` | Record a click event and redirect to original URL |
| GET | `/preview/<short_code>` | `200` | Record an impression and render link preview |
| GET | `/p/<short_code>` | `200` | Shorthand alias for the link preview endpoint |
| GET | `/i/<short_code>.gif` | `200` | Record an impression and return 1x1 transparent GIF |
| POST | `/api/urls/<short_code>/impression` | `201` | Programmatic API to log an impression |

### URL Creation Example

```json
POST /api/urls
Content-Type: application/json

{
  "original_url": "https://example.com/docs",
  "custom_alias": "docs"
}
```

Response:
```json
{
  "id": 1,
  "user_id": 1,
  "original_url": "https://example.com/docs",
  "short_code": "docs",
  "custom_alias": "docs",
  "short_url": "http://127.0.0.1:5000/docs",
  "preview_url": "http://127.0.0.1:5000/preview/docs",
  "created_at": "2026-09-24T12:00:00+00:00",
  "updated_at": "2026-09-24T12:00:00+00:00"
}
```

## Analytics Endpoints

All analytics endpoints require authentication and enforce URL ownership.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/urls/<id>/analytics` | Overview metrics for one owned URL |
| GET | `/api/urls/<id>/analytics/overview` | Explicit overview metrics endpoint |
| GET | `/api/urls/<id>/analytics/timeseries` | Clicks and impressions bucketed by day (`?granularity=day`) or hour (`?granularity=hour`) |
| GET | `/api/urls/<id>/analytics/devices` | Clicks breakdown by device type (`Desktop`, `Mobile`, `Tablet`, `Unknown`) |
| GET | `/api/urls/<id>/analytics/referrers` | Clicks breakdown by HTTP `Referer` |
| GET | `/api/urls/<id>/analytics/countries` | Clicks, impressions, and CTR breakdown by ISO country code |
| GET | `/api/analytics/urls/top` | Authenticated user's URLs ranked by click volume with impressions and CTR |
| GET | `/api/analytics/summary` | Consolidated batch summary of all owned URLs (eliminating dashboard N+1 queries) |

### Sample Analytics Responses

#### Overview (`/api/urls/<id>/analytics/overview`)

```json
{
  "total_clicks": 142,
  "total_impressions": 350,
  "ctr": 40.57,
  "first_click": "2026-09-24T10:15:00+00:00",
  "latest_click": "2026-09-24T12:30:00+00:00",
  "first_impression": "2026-09-24T09:00:00+00:00",
  "latest_impression": "2026-09-24T12:30:00+00:00",
  "most_common_device_type": "Desktop",
  "most_common_referrer": "https://news.ycombinator.com"
}
```

*Note: If `total_impressions` is 0, `ctr` returns `null` to represent an undefined calculation without throwing division-by-zero errors.*

#### Timeseries (`/api/urls/<id>/analytics/timeseries?granularity=day`)

```json
[
  {
    "date": "2026-09-24T00:00:00+00:00",
    "clicks": 42,
    "impressions": 100,
    "ctr": 42.0
  }
]
```

#### Countries (`/api/urls/<id>/analytics/countries`)

```json
[
  {
    "country": "US",
    "clicks": 80,
    "impressions": 160,
    "ctr": 50.0
  },
  {
    "country": "DE",
    "clicks": 25,
    "impressions": 50,
    "ctr": 50.0
  }
]
```

#### Summary (`/api/analytics/summary`)

```json
[
  {
    "id": 1,
    "short_code": "docs",
    "total_clicks": 142,
    "total_impressions": 350,
    "ctr": 40.57
  }
]
```