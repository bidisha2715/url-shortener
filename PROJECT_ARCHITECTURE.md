# Project Architecture

## Production Architecture

```text
Browser Client (React 19 + Vite)
       │
       │ JSON over HTTP (credentials: 'include')
       ▼
Gunicorn WSGI Server (Procfile: web: gunicorn 'app:create_app()')
       │
       ▼
Flask Application Factory (app:create_app())
       │
       ├── Werkzeug ProxyFix (configured via TRUSTED_PROXY_COUNT)
       ├── Session-Based Authentication (app/auth.py)
       ├── URL CRUD & Management (app/urls.py)
       ├── Redirect Handler (/<short_code>)
       ├── Link Preview & Impression Logging (/preview/<short_code>, /p/<short_code>)
       ├── Impression Tracking Pixel (/i/<short_code>.gif)
       ├── Analytics Services (/api/urls/<id>/analytics/*, /api/analytics/*)
       └── GeoIP Engine (CDN header parser + local MaxMind mmdb reader)
       │
       ▼
PostgreSQL Database (psycopg v3 via app/db.py)
       ├── users
       ├── urls
       ├── clicks (url_id, timestamp, ip_address, device_type, country, referrer)
       ├── impressions (url_id, timestamp, ip_address, device_type, country, referrer)
       └── audit_logs
```

## Legacy Materials

`run.py`, `templates/`, and `static/` are preserved solely as legacy reference. The active, production-ready system is the Flask application factory connected to PostgreSQL with the React client.

## React Client

The React application in `frontend/` provides:
- Authentication state management (`frontend/src/auth/AuthContext.jsx`)
- URL management dashboard with create, edit, delete, and copy features (`frontend/src/pages/DashboardPage.jsx`)
- Single-request batch summary stats integration (`/api/analytics/summary`)
- Interactive, responsive analytics dashboard (`frontend/src/pages/AnalyticsPlaceholderPage.jsx`) displaying total clicks, impressions, CTR, activity over time, device breakdowns, referrers, and country distributions.

## Event Tracking & Analytics

1. **Impressions:** Captured when a user accesses the public preview page (`/preview/<short_code>`), loads an embed beacon (`/i/<short_code>.gif`), or triggers the programmatic API.
2. **Clicks:** Captured when a visitor accesses `/<short_code>`, recording client IP, device classification, country, and referrer before executing an HTTP 302 redirect.
3. **CTR Calculation:** $\text{CTR} = (\text{clicks} / \text{impressions}) \times 100$. If impressions = 0, CTR returns `null`.
4. **Geography:** Country is resolved to a 2-letter ISO code using trusted edge headers or offline MaxMind databases.