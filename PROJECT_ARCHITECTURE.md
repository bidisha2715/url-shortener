# Project Architecture

## Current Stage

```text
Browser
   |
   v
Flask REST API
   |
   v
Flask session authentication
   |
   v
URL route handlers
   |
   v
PostgreSQL through app/db.py
   |
   +--> users
   +--> urls
   +--> clicks
   +--> audit_logs
```

The React frontend will be added later. For now, the Flask app factory exposes the PostgreSQL API while the original SQLite application remains available through `run.py` as a rollback path.

## React foundation

The Stage 4 frontend is isolated in `frontend/` and uses React, JavaScript, and Vite. Its development server runs on `http://127.0.0.1:5173`; Vite proxies `/api` requests to the Flask API at `http://127.0.0.1:5000`. `frontend/src/services/api.js` is the centralized request helper and includes Flask session credentials. Existing Jinja templates, static files, and backend modules remain in place during the gradual migration.

## Ownership

The session stores the authenticated user's ID. URL queries filter by that ID, and detail, update, and delete operations compare the URL owner before changing anything. A client cannot select another user by sending a different `user_id` because the API never accepts ownership from the request body.

## Redirect and Click Flow

`GET /<short_code>` finds the URL by its unique code, inserts a timestamped click event with the request IP, a simple device category, and the optional referrer, commits, and sends an HTTP redirect. Raw IP data stays in PostgreSQL and is not returned by analytics.

## Analytics

Analytics routes use PostgreSQL `COUNT`, `MIN`, `MAX`, `date_trunc`, `GROUP BY`, and `LEFT JOIN` queries over real click rows. Every URL-scoped query passes through the same ownership check used by URL CRUD. Country is nullable because there is no configured geolocation provider. CTR is intentionally absent because there is no impressions event.