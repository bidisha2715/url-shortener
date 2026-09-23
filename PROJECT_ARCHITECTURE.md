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
```

The React frontend will be added later. For now, the Flask app factory exposes the PostgreSQL API while the original SQLite application remains available through `run.py` as a rollback path.

## Ownership

The session stores the authenticated user's ID. URL queries filter by that ID, and detail, update, and delete operations compare the URL owner before changing anything. A client cannot select another user by sending a different `user_id` because the API never accepts ownership from the request body.

## Redirect and Click Flow

`GET /<short_code>` finds the URL by its unique code, inserts a timestamped row into `clicks`, commits both operations, and sends an HTTP redirect. The click table is separate from `urls`, so later analytics can group real events without inventing a counter or visitor metadata.