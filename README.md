# URL Shortener

This repository contains a full-stack URL shortener powered by a Flask application factory (`app:create_app()`), a PostgreSQL database, and a modern React client (`frontend/`). The system supports cookie-based session authentication, owned URL CRUD, generated short codes, custom aliases, direct redirects, public preview pages, event-based impression tracking, genuine Click-Through Rate (CTR) analytics, and country-level geographic analytics.

The legacy monolithic SQLite application (`run.py`, `templates/`, and `static/`) is retained strictly as legacy reference material. The active production backend is the Flask application factory connected to PostgreSQL, served via Gunicorn.

## Architecture Overview

```text
Browser Client (React + Vite)
       │
       │ JSON requests (credentials: 'include')
       ▼
Flask Application Factory (app:create_app())
       │
       ├── Authentication Blueprint (/api/auth/*)
       ├── URL & Analytics Blueprint (/api/urls/*, /api/analytics/*)
       ├── Direct Redirect Handler (/<short_code>)
       ├── Public Preview / Impression Handler (/preview/<short_code>, /p/<short_code>)
       ├── Impression Tracking Pixel (/i/<short_code>.gif)
       └── GeoIP & Safe Proxy Layer (CDN headers / MaxMind mmdb)
       │
       ▼
PostgreSQL Database (psycopg v3)
       ├── users
       ├── urls
       ├── clicks
       ├── impressions
       └── audit_logs
```

## Run Locally

### 1. Backend Setup

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Create `.env` from `.env.example`:
   ```bash
   cp .env.example .env
   ```
   Set `DATABASE_URL` (PostgreSQL connection string) and `SECRET_KEY`. Optionally set `GEOIP_DATABASE_PATH` (path to a local MaxMind `.mmdb` file) and `TRUSTED_PROXY_COUNT`.
3. Initialize the PostgreSQL schema:
   ```bash
   python setup_postgres.py
   ```
4. Start the Flask API:
   ```bash
   flask --app 'app:create_app()' run --debug --port 5000
   ```

### 2. Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
2. The React client runs at `http://127.0.0.1:5173`. Vite proxies `/api` calls directly to the Flask backend running on port 5000.

### 3. Production Deployment

Production process management is defined in `Procfile`:
```text
web: gunicorn 'app:create_app()'
```
Gunicorn executes the modern Flask application factory. Reverse proxies (e.g. Nginx, Cloudflare) can be configured safely via `TRUSTED_PROXY_COUNT` in `.env` to enable Werkzeug's `ProxyFix`.

---

## CTR & Impression Model

### Definitions
* **Impression:** A view or render of the short URL preview or embed. An impression event is recorded in the `impressions` table when a visitor views the public preview page (`/preview/<short_code>` or `/p/<short_code>`), loads an embed beacon (`/i/<short_code>.gif`), or triggers the impression API (`POST /api/urls/<short_code>/impression`).
* **Click:** An intentional navigation event to the target destination. A click event is recorded in the `clicks` table when a visitor accesses `/<short_code>` (either directly or by clicking "Visit destination" on the preview page).
* **Click-Through Rate (CTR):**
  $$\text{CTR} = \left(\frac{\text{clicks}}{\text{impressions}}\right) \times 100\%$$
  If $\text{impressions} = 0$, CTR is reported as `null` (`None` in Python, serialized as `null` in JSON) to prevent division by zero.

---

## Real Geographic Analytics

* **Performance Guarantee:** Country resolution never performs synchronous external HTTP calls during redirects. All lookups occur in-memory from trusted CDN headers or via local binary databases (`.mmdb`).
* **Resolution Pipeline:**
  1. **Trusted CDN / Edge Headers:** Inspects headers such as `CF-IPCountry`, `CloudFront-Viewer-Country`, and `X-Country-Code`. If a valid 2-letter ISO 3166-1 alpha-2 code is present, it is recorded.
  2. **Local MaxMind GeoLite2 Database:** If `GEOIP_DATABASE_PATH` points to a local MaxMind Country or City database file, IP lookups are resolved offline.
  3. **Localhost / Private IP Safety:** Private subnets (RFC 1918) and loopback addresses (`127.0.0.1`, `::1`) are recognized and gracefully handled without false country assignments.
  4. **Privacy:** Raw visitor IP addresses are stored privately in PostgreSQL for operational analysis and are **never** returned through public analytics endpoints.

---

## Running Automated Tests

Run the test suite with:

```bash
python -m pytest -q
```

The automated test suite runs against a comprehensive test double that validates authentication, URL CRUD, collision handling, ownership enforcement, redirects, impression logging, CTR calculations, zero-impression safety, geographic resolution, CDN headers, and proxy safety.
