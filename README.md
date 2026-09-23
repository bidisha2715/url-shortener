# URL Shortener

This repository contains a Flask URL shortener with a PostgreSQL API. The current backend supports session authentication, owned URL CRUD, generated short codes, custom aliases, redirects, and click-event analytics. React is intentionally not part of the current stage.

## Run locally

1. Install dependencies with `pip install -r requirements.txt`.
2. Create a local `.env` from `.env.example` and set `DATABASE_URL` and `SECRET_KEY`.
3. Create the PostgreSQL database, then run `python setup_postgres.py`.
4. Start the API with `flask --app 'app:create_app()' run --debug`.

The active API uses PostgreSQL. `run.py` and the older templates are retained as legacy material and are not the Stage 3 API entry point.

## Stage 3 analytics

Opening a short URL writes one row to `clicks` with its URL ID, PostgreSQL timestamp, request IP, a best-effort device category, and the optional HTTP `Referer` value. Analytics are calculated from those rows. Raw IP addresses are not returned in analytics responses.

Available analytics endpoints are documented in [API.md](API.md). They include overview, daily or hourly time series, device counts, referrer counts, country data when available, and the logged-in user's most-clicked URLs. Country data is empty unless a real provider populates `clicks.country`; no geographic values are fabricated. CTR is not calculated because impressions are not modeled.

Database query explanations are in [DATABASE.md](DATABASE.md), index and query-plan notes are in [PERFORMANCE.md](PERFORMANCE.md), and security/privacy decisions are in [SECURITY.md](SECURITY.md).

## Tests

Run the backend test suite with:

```text
python -m pytest -q
```

The tests use a database double for fast route coverage. Manual PostgreSQL verification is still required for query plans and real deployment behavior.

## Stage 4 frontend foundation

The React client lives in `frontend/` and is intentionally separate from the existing Flask templates and legacy static files. From the repository root:

```text
cd frontend
npm install
npm run dev
```

The frontend runs at `http://127.0.0.1:5173`. Start the Flask API separately at `http://127.0.0.1:5000` with `flask --app 'app:create_app()' run --debug`. Vite proxies frontend requests beginning with `/api` to Flask, so browser requests can use relative API paths. The shared API helper sends `credentials: 'include'` for Flask's session cookie.

This stage provides only the React shell and a placeholder page. URL management, authentication screens, and analytics UI will be migrated after the foundation is manually verified.

### Stage 4.2 authentication

The React login and registration pages call Flask's existing `POST /api/auth/login`, `POST /api/auth/register`, and `POST /api/auth/logout` endpoints. Requests use `credentials: 'include'`, so Flask's signed HTTP-only session cookie remains the source of authentication. On refresh, the frontend checks the protected `GET /api/urls` endpoint: a successful response restores an authenticated state and `401` returns the user to the login flow. No JWT or password storage is used.
