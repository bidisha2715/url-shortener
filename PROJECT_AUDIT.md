# Project Audit

Audit date: 2026-09-23

This audit describes the repository as found before the migration. It records verified code and files, not claims about production behavior.

## Executive Summary

The project currently contains two different Flask implementations:

- `run.py` is a monolithic Flask application with form-based authentication, URL creation, redirects, dashboard, analytics, edit, and delete routes.
- `app/routes.py` is a separate Flask blueprint with its own SQLite initialization, public shortening API, redirect, basic stats page, and stats API.
- `app/__init__.py` registers only the blueprint. The current `Procfile` launches `run.py` directly, so the app-factory route set is not the route set used by the Procfile.

The application is SQLite-based and server-rendered with Jinja templates. It is not currently a React/PostgreSQL application. Several existing paths are incomplete or inconsistent, so the migration should first establish one application entry point and one schema.

## What Currently Exists

### Verified useful functionality

- Flask application startup through `run.py` on port `10000`.
- A second app-factory startup path through `app.create_app()`.
- Form pages for registration, login, URL creation, dashboard, and analytics.
- URL validation that accepts strings beginning with `http://` or `https://` in `run.py`.
- Random six-character short-code generation using letters and digits.
- Custom aliases in the `run.py` home route.
- Redirects that increment a single integer click counter.
- Dashboard listing for links associated with the logged-in username in `run.py`.
- Basic edit and delete route definitions in `run.py`.
- JSON endpoints `/api/shorten` and `/api/stats/<short>` in the blueprint implementation.
- Browser-side clipboard copying, keyboard shortcuts, reveal animations, and alert dismissal in `static/script.js`.
- Render deployment configuration through `Procfile` and a Gunicorn dependency.

### Verified incomplete or unsafe behavior

- Passwords are stored and compared as plaintext in `run.py` and in the live database.
- The Flask session secret is hardcoded as `secret123`.
- There is no environment-variable configuration.
- The live database contains users and URLs, but the schema is not relational: `urls.username` is plain text and has no foreign key.
- `setup_db.py` creates a different `urls` schema (`original`, `short`, and no `username`) than either `run.py` or `app/routes.py` expects.
- `app/routes.py` initializes another incompatible schema (`original`, `short`, `clicks`) at import time.
- Generated codes in `run.py` are not checked for collision before insertion. The blueprint version does check collisions, but these implementations are separate.
- The blueprint home route and `/api/shorten` do not validate URL format, require authentication, or support ownership.
- `/stats/<code>` in `run.py` does not verify that the requested link belongs to the logged-in user. The blueprint stats routes are public.
- Edit and delete in `run.py` check that a user is logged in but do not filter the target URL by the logged-in owner.
- Edit uses `templates/edit.html`, but that file is absent from the repository, so the GET edit path raises a template-not-found error.
- Edit does not validate alias uniqueness or ownership and only changes the code, not the destination URL.
- Delete uses a GET request and does not verify ownership.
- Redirect tracking stores only a counter; it does not create click records, timestamps, device data, referrers, or countries.
- The analytics template calculates `Engagements` as `clicks * 1.2`. There is no impressions or engagement event model, so this is not a meaningful metric and must not be retained as a real claim.
- The `run.py` redirect can read a URL from a row and update it using a separate query without a transaction-safe increment strategy.
- Broad exception handling during registration hides all database errors as “User already exists.”
- Templates use server-rendered forms and Jinja; there is no React source tree or `package.json`.
- No automated test suite is present in the repository.
- The README describes `edit.html`, but the file is not present. Its live-demo text is a documentation claim that has not been independently verified in this audit.

## Current Architecture

```text
Browser
  |
  +--> run.py --> Flask routes --> sqlite3 --> database.db
  |
  +--> app.create_app() --> app/routes.py blueprint --> sqlite3 --> database.db
```

The two backend paths share the same SQLite file but not the same table naming or column conventions. The frontend is a collection of Jinja HTML templates with one shared CSS file and one shared JavaScript file.

## Current Routes

### Routes in `run.py`

| Method | Path | Purpose |
|---|---|---|
| GET, POST | `/register` | Register using username and plaintext password |
| GET, POST | `/login` | Login using username and plaintext password |
| GET | `/logout` | Remove the session username |
| GET, POST | `/` | Authenticated URL creation with optional custom alias |
| GET | `/<code>` | Redirect and increment the URL counter |
| GET | `/dashboard` | List links for the session username |
| GET | `/stats/<code>` | Render basic link statistics |
| GET, POST | `/edit/<code>` | Render missing edit template or update code |
| GET | `/delete/<code>` | Delete a URL row |

### Routes in `app/routes.py`

| Method | Path | Purpose |
|---|---|---|
| GET, POST | `/` | Public form shortening against the blueprint schema |
| GET | `/<short>` | Redirect and increment the blueprint counter |
| GET | `/stats/<code>` | Render basic statistics |
| POST | `/api/shorten` | Public JSON shortening |
| GET | `/api/stats/<short>` | Public JSON statistics |

`app.create_app()` currently registers the second route set only. `run.py` does not import or use `create_app()`.

## Current Database Structure

The live `database.db` was inspected directly. It contains:

```sql
CREATE TABLE urls (
    short_code TEXT PRIMARY KEY,
    original_url TEXT,
    clicks INTEGER,
    username TEXT
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
);
```

The database contains seven URL rows and three user rows at audit time. The stored user passwords are plaintext. There are no click-event, audit-log, timestamp, email, or foreign-key columns.

The schema created by `setup_db.py` is different:

```sql
CREATE TABLE urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original TEXT UNIQUE,
    short TEXT UNIQUE,
    clicks INTEGER DEFAULT 0
);
```

This script drops only `urls`, which can leave the `users` table in place, and it does not produce the schema required by `run.py`.

## Dependencies and Deployment

`requirements.txt` contains only:

- Flask
- gunicorn

The source imports `psycopg2` in `app/routes.py`, but no PostgreSQL driver is listed as a dependency and that import is unused. The deployment file contains `web: python run.py`, which starts Flask's built-in development server configuration from `run.py`, not Gunicorn despite the README mentioning Gunicorn.

## Proposed Architecture

```text
React frontend
      |
      | JSON over HTTP
      v
Flask application factory
      |
      +--> API route modules
      +--> authentication and ownership helpers
      +--> URL and analytics services
      v
PostgreSQL via a small, explicit database layer
```

The first implementation should keep the boundaries understandable:

- one Flask application factory and one backend entry point;
- API routes separated from service logic;
- parameterized SQL or a small database abstraction, rather than multiple ad-hoc connection patterns;
- PostgreSQL tables for users, URLs, click events, and audit logs;
- hashed passwords and environment-based configuration;
- React pages for authentication, dashboard, URL management, and analytics;
- click analytics based on actual click rows, with no CTR unless impressions are modeled.

The existing visual language can be used as a starting point, but templates should be replaced incrementally after the API contract is stable.

## Migration Plan

1. **Audit and baseline:** preserve this document, confirm the current route/schema split, and avoid treating the existing README claims as verified behavior.
2. **Backend foundation:** add configuration from environment variables, choose one Flask entry point, add PostgreSQL connection handling, and create a safe schema initialization or migration mechanism.
3. **Authentication:** add users with password hashes, session or token-based API authentication, validation, and consistent JSON error responses.
4. **URL service:** implement validated creation, collision-safe generated codes, custom alias conflicts, ownership checks, update, delete, and redirects.
5. **Click analytics:** replace the counter as the source of truth with click-event rows. Store only technically available and privacy-appropriate request metadata; do not invent geographic data.
6. **REST API:** implement and document the requested auth, URL, redirect, and analytics endpoints with correct status codes and authorization behavior.
7. **Tests:** add focused backend tests for authentication, validation, ownership, aliases, redirects, click events, CRUD, and analytics.
8. **React frontend:** introduce a separate frontend only after the API contract works, then port the useful create/list/edit/delete/copy flows.
9. **Documentation and performance:** document schema normalization, SQL analytics queries, real indexes, query-plan evidence when available, security decisions, limitations, and interview notes. Do not add benchmark or production claims without measurements.
10. **Deployment verification:** update the process configuration and environment setup for the chosen PostgreSQL deployment, then run the documented tests and manual checks.

## Approval Gate

This audit is complete. No application behavior was changed as part of Phase 1. Before the migration begins, confirm the proposed architecture and whether to use:

- cookie-based Flask sessions for the React frontend, or
- a token-based API login flow.

The simpler interview-friendly default is cookie-based sessions when the frontend and API are served from the same site; a token flow is useful when they are deployed on separate origins but introduces more security and lifecycle details to explain.