from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from app import auth, urls


class Result:
    def __init__(self, rows=None, row=None):
        self.rows = rows or []
        self.row = row

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeDatabase:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.users = {1: {"id": 1, "username": "alice", "email": "alice@example.com"}}
        self.urls = {}
        self.clicks = []
        self.next_url_id = 1
        self.now = now

    def execute(self, query, params=()):
        query = " ".join(query.split())
        if query.startswith("SELECT id, username, email FROM users"):
            return Result(row=self.users.get(params[0]))
        if query.startswith("SELECT id FROM urls WHERE short_code"):
            match = next((row for row in self.urls.values() if row["short_code"] == params[0] or row["custom_alias"] == params[1]), None)
            return Result(row={"id": match["id"]} if match else None)
        if query.startswith("SELECT id, user_id, original_url") and "WHERE id =" in query:
            return Result(row=self.urls.get(params[0]))
        if query.startswith("SELECT id, user_id, original_url") and "WHERE user_id =" in query:
            return Result(rows=[row for row in self.urls.values() if row["user_id"] == params[0]])
        if query.startswith("SELECT id, original_url FROM urls"):
            return Result(row=next((row for row in self.urls.values() if row["short_code"] == params[0]), None))
        if query.startswith("INSERT INTO urls"):
            user_id, original_url, short_code, custom_alias = params
            if any(row["short_code"] == short_code for row in self.urls.values()):
                from psycopg.errors import UniqueViolation
                raise UniqueViolation("duplicate short code")
            row = {
                "id": self.next_url_id,
                "user_id": user_id,
                "original_url": original_url,
                "short_code": short_code,
                "custom_alias": custom_alias,
                "created_at": self.now,
                "updated_at": self.now,
            }
            self.urls[self.next_url_id] = row
            self.next_url_id += 1
            return Result(row=row)
        if query.startswith("UPDATE urls"):
            original_url, short_code, custom_alias, url_id, user_id = params
            row = self.urls[url_id]
            if any(other["short_code"] == short_code and other["id"] != url_id for other in self.urls.values()):
                from psycopg.errors import UniqueViolation
                raise UniqueViolation("duplicate short code")
            row.update(original_url=original_url, short_code=short_code, custom_alias=custom_alias, updated_at=self.now)
            return Result(row=row)
        if query.startswith("DELETE FROM urls"):
            self.urls.pop(params[0], None)
            return Result()
        if query.startswith("INSERT INTO clicks"):
            self.clicks.append({
                "url_id": params[0],
                "timestamp": self.now,
                "ip_address": params[1] if len(params) > 1 else None,
                "device_type": params[2] if len(params) > 2 else None,
                "referrer": params[3] if len(params) > 3 else None,
                "country": None,
            })
            return Result()
        if query.startswith("SELECT COUNT(*) AS total_clicks"):
            clicks = [click for click in self.clicks if click["url_id"] == params[0]]
            return Result(row={
                "total_clicks": len(clicks),
                "first_click": min((click["timestamp"] for click in clicks), default=None),
                "latest_click": max((click["timestamp"] for click in clicks), default=None),
            })
        if "GROUP BY COALESCE(NULLIF(device_type" in query:
            counts = {}
            for click in self.clicks:
                if click["url_id"] == params[0]:
                    device = click["device_type"] or "Unknown"
                    counts[device] = counts.get(device, 0) + 1
            rows = [{"device_type": device, "clicks": count} for device, count in counts.items()]
            rows.sort(key=lambda row: (-row["clicks"], row["device_type"]))
            return Result(row=rows[0] if "LIMIT 1" in query and rows else None, rows=rows)
        if query.startswith("SELECT referrer, COUNT(*)"):
            counts = {}
            for click in self.clicks:
                if click["url_id"] == params[0] and click["referrer"]:
                    counts[click["referrer"]] = counts.get(click["referrer"], 0) + 1
            rows = [{"referrer": referrer, "clicks": count} for referrer, count in counts.items()]
            rows.sort(key=lambda row: (-row["clicks"], row["referrer"] == "Unknown", row["referrer"]))
            return Result(row=rows[0] if rows else None)
        if query.startswith("SELECT date_trunc"):
            buckets = {}
            for click in self.clicks:
                if click["url_id"] == params[0]:
                    timestamp = click["timestamp"]
                    bucket = timestamp.replace(minute=0, second=0, microsecond=0) if "'hour'" in query else timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                    buckets[bucket] = buckets.get(bucket, 0) + 1
            return Result(rows=[{"bucket": bucket, "clicks": count} for bucket, count in sorted(buckets.items())])
        if "SELECT COALESCE(NULLIF(referrer, ''), 'Unknown')" in query:
            counts = {}
            for click in self.clicks:
                if click["url_id"] == params[0]:
                    referrer = click["referrer"] or "Unknown"
                    counts[referrer] = counts.get(referrer, 0) + 1
            rows = [{"referrer": referrer, "clicks": count} for referrer, count in counts.items()]
            rows.sort(key=lambda row: (-row["clicks"], row["referrer"] == "Unknown", row["referrer"]))
            return Result(rows=rows)
        if query.startswith("SELECT country, COUNT(*)"):
            counts = {}
            for click in self.clicks:
                if click["url_id"] == params[0] and click["country"]:
                    counts[click["country"]] = counts.get(click["country"], 0) + 1
            return Result(rows=[{"country": country, "clicks": count} for country, count in counts.items()])
        if query.startswith("SELECT u.short_code"):
            rows = []
            for url in self.urls.values():
                if url["user_id"] == params[0]:
                    rows.append({
                        "short_code": url["short_code"],
                        "original_url": url["original_url"],
                        "total_clicks": sum(click["url_id"] == url["id"] for click in self.clicks),
                    })
            return Result(rows=sorted(rows, key=lambda row: -row["total_clicks"]))
        raise AssertionError(f"Unhandled SQL in test double: {query}")

    def commit(self):
        pass

    def rollback(self):
        pass


@pytest.fixture
def client(monkeypatch):
    database = FakeDatabase()
    monkeypatch.setattr(auth, "get_db", lambda: database)
    monkeypatch.setattr(urls, "get_db", lambda: database)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    with app.test_client() as test_client:
        with test_client.session_transaction() as session:
            session["user_id"] = 1
        yield test_client, database


def create_payload(client, original_url="https://example.com"):
    return client.post("/api/urls", json={"original_url": original_url})


def test_unauthenticated_creation_is_rejected(monkeypatch):
    database = FakeDatabase()
    monkeypatch.setattr(auth, "get_db", lambda: database)
    monkeypatch.setattr(urls, "get_db", lambda: database)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    with app.test_client() as client:
        response = client.post("/api/urls", json={"original_url": "https://example.com"})
    assert response.status_code == 401


def test_create_generated_url(client):
    test_client, database = client
    response = create_payload(test_client)
    assert response.status_code == 201
    assert len(response.json["short_code"]) == 6
    assert len(database.urls) == 1


def test_custom_alias_and_duplicate_alias(client):
    test_client, _database = client
    first = test_client.post("/api/urls", json={"original_url": "https://example.com", "custom_alias": "docs"})
    duplicate = test_client.post("/api/urls", json={"original_url": "https://other.example", "custom_alias": "docs"})
    assert first.status_code == 201
    assert duplicate.status_code == 409


def test_invalid_url_is_rejected(client):
    response = create_payload(client[0], "not-a-url")
    assert response.status_code == 400


def test_list_get_update_and_delete_are_owned(client):
    test_client, database = client
    created = create_payload(test_client).json
    url_id = created["id"]
    assert test_client.get("/api/urls").status_code == 200
    assert test_client.get(f"/api/urls/{url_id}").status_code == 200
    updated = test_client.put(f"/api/urls/{url_id}", json={"original_url": "https://updated.example"})
    assert updated.status_code == 200
    deleted = test_client.delete(f"/api/urls/{url_id}")
    assert deleted.status_code == 200
    assert url_id not in database.urls


def test_other_user_cannot_access_url(client):
    test_client, database = client
    created = create_payload(test_client).json
    database.users[2] = {"id": 2, "username": "bob", "email": "bob@example.com"}
    database.urls[created["id"]]["user_id"] = 2
    assert test_client.get(f"/api/urls/{created['id']}").status_code == 403
    assert test_client.put(f"/api/urls/{created['id']}", json={"original_url": "https://no.example"}).status_code == 403
    assert test_client.delete(f"/api/urls/{created['id']}").status_code == 403


def test_redirect_records_click(client):
    test_client, database = client
    created = create_payload(test_client).json
    response = test_client.get(f"/{created['short_code']}")
    assert response.status_code == 302
    assert response.location == "https://example.com"
    assert database.clicks[0]["url_id"] == created["id"]
    assert database.clicks[0]["device_type"] == "Desktop"
    assert database.clicks[0]["referrer"] is None


def test_device_detection_categories():
    assert urls.detect_device_type("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile") == "Mobile"
    assert urls.detect_device_type("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X)") == "Tablet"
    assert urls.detect_device_type("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit") == "Desktop"
    assert urls.detect_device_type("") == "Unknown"


def test_click_metadata_and_analytics_endpoints(client):
    test_client, database = client
    created = create_payload(test_client).json
    test_client.get(f"/{created['short_code']}", headers={"User-Agent": "Mozilla/5.0 (iPhone) Mobile", "Referer": "https://google.com"})
    database.now += timedelta(hours=1)
    test_client.get(f"/{created['short_code']}", headers={"User-Agent": "Mozilla/5.0 (iPad)"})

    overview = test_client.get(f"/api/urls/{created['id']}/analytics").json
    assert overview["total_clicks"] == 2
    assert overview["first_click"] is not None
    assert overview["latest_click"] is not None
    assert overview["most_common_device_type"] == "Mobile"
    assert overview["most_common_referrer"] == "https://google.com"
    assert test_client.get(f"/api/urls/{created['id']}/analytics/overview").json == overview
    assert test_client.get(f"/api/urls/{created['id']}/analytics/timeseries").json[0]["clicks"] == 2
    assert test_client.get(f"/api/urls/{created['id']}/analytics/devices").json == [
        {"device_type": "Mobile", "clicks": 1}, {"device_type": "Tablet", "clicks": 1}
    ]
    assert test_client.get(f"/api/urls/{created['id']}/analytics/referrers").json == [
        {"referrer": "https://google.com", "clicks": 1}, {"referrer": "Unknown", "clicks": 1}
    ]
    assert test_client.get(f"/api/urls/{created['id']}/analytics/countries").json == []


def test_empty_analytics_and_most_clicked_urls(client):
    test_client, _database = client
    first = create_payload(test_client, "https://first.example").json
    second = test_client.post("/api/urls", json={"original_url": "https://second.example"}).json
    assert test_client.get(f"/api/urls/{first['id']}/analytics").json["total_clicks"] == 0
    assert test_client.get(f"/api/urls/{first['id']}/analytics/timeseries").json == []
    assert test_client.get("/api/analytics/urls/top").json == [
        {"short_code": first["short_code"], "original_url": "https://first.example", "total_clicks": 0},
        {"short_code": second["short_code"], "original_url": "https://second.example", "total_clicks": 0},
    ]


def test_analytics_ownership(client):
    test_client, database = client
    created = create_payload(test_client).json
    database.users[2] = {"id": 2, "username": "bob", "email": "bob@example.com"}
    database.urls[created["id"]]["user_id"] = 2
    assert test_client.get(f"/api/urls/{created['id']}/analytics").status_code == 403