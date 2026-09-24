from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from app import auth, urls
from app.geoip import (
    get_client_ip,
    is_private_ip,
    is_valid_iso_country,
    resolve_country,
    set_custom_resolver,
    reset_custom_resolver,
)


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
        self.impressions = []
        self.next_url_id = 1
        self.now = now

    def execute(self, query, params=()):
        query = " ".join(query.split())
        if query.startswith("SELECT id, username, email FROM users"):
            return Result(row=self.users.get(params[0]))
        if query.startswith("SELECT id FROM urls WHERE short_code"):
            match = next((row for row in self.urls.values() if row["short_code"] == params[0] or row.get("custom_alias") == params[0]), None)
            return Result(row={"id": match["id"]} if match else None)
        if query.startswith("SELECT id, original_url, short_code FROM urls WHERE short_code"):
            match = next((row for row in self.urls.values() if row["short_code"] == params[0] or row.get("custom_alias") == params[0]), None)
            return Result(row=match)
        if query.startswith("SELECT id, user_id, original_url") and "WHERE id =" in query:
            return Result(row=self.urls.get(params[0]))
        if query.startswith("SELECT id, user_id, original_url") and "WHERE user_id =" in query:
            return Result(rows=[row for row in self.urls.values() if row["user_id"] == params[0]])
        if query.startswith("SELECT id, original_url FROM urls"):
            return Result(row=next((row for row in self.urls.values() if row["short_code"] == params[0] or row.get("custom_alias") == params[0]), None))
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
        if query.startswith("INSERT INTO impressions"):
            self.impressions.append({
                "url_id": params[0],
                "timestamp": self.now,
                "ip_address": params[1] if len(params) > 1 else None,
                "device_type": params[2] if len(params) > 2 else None,
                "country": params[3] if len(params) > 3 else None,
                "referrer": params[4] if len(params) > 4 else None,
            })
            return Result()
        if query.startswith("INSERT INTO clicks"):
            self.clicks.append({
                "url_id": params[0],
                "timestamp": self.now,
                "ip_address": params[1] if len(params) > 1 else None,
                "device_type": params[2] if len(params) > 2 else None,
                "country": params[3] if len(params) > 3 else None,
                "referrer": params[4] if len(params) > 4 else None,
            })
            return Result()
        if query.startswith("SELECT COUNT(*) AS total_clicks"):
            clicks = [click for click in self.clicks if click["url_id"] == params[0]]
            return Result(row={
                "total_clicks": len(clicks),
                "first_click": min((click["timestamp"] for click in clicks), default=None),
                "latest_click": max((click["timestamp"] for click in clicks), default=None),
            })
        if query.startswith("SELECT COUNT(*) AS total_impressions"):
            impressions = [imp for imp in self.impressions if imp["url_id"] == params[0]]
            return Result(row={
                "total_impressions": len(impressions),
                "first_impression": min((imp["timestamp"] for imp in impressions), default=None),
                "latest_impression": max((imp["timestamp"] for imp in impressions), default=None),
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
        if "WITH click_buckets AS" in query and "impression_buckets AS" in query:
            url_id = params[0]
            buckets = {}
            for click in self.clicks:
                if click["url_id"] == url_id:
                    timestamp = click["timestamp"]
                    b = timestamp.replace(minute=0, second=0, microsecond=0) if "'hour'" in query else timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                    buckets.setdefault(b, {"bucket": b, "clicks": 0, "impressions": 0})
                    buckets[b]["clicks"] += 1
            for imp in self.impressions:
                if imp["url_id"] == url_id:
                    timestamp = imp["timestamp"]
                    b = timestamp.replace(minute=0, second=0, microsecond=0) if "'hour'" in query else timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                    buckets.setdefault(b, {"bucket": b, "clicks": 0, "impressions": 0})
                    buckets[b]["impressions"] += 1
            rows = sorted(buckets.values(), key=lambda r: r["bucket"])
            return Result(rows=rows)
        if "WITH click_countries AS" in query and "impression_countries AS" in query:
            url_id = params[0]
            c_dict = {}
            for click in self.clicks:
                if click["url_id"] == url_id and click.get("country"):
                    c = click["country"]
                    c_dict.setdefault(c, {"country": c, "clicks": 0, "impressions": 0})
                    c_dict[c]["clicks"] += 1
            for imp in self.impressions:
                if imp["url_id"] == url_id and imp.get("country"):
                    c = imp["country"]
                    c_dict.setdefault(c, {"country": c, "clicks": 0, "impressions": 0})
                    c_dict[c]["impressions"] += 1
            rows = sorted(c_dict.values(), key=lambda r: (-r["clicks"], -r["impressions"], r["country"]))
            return Result(rows=rows)
        if "SELECT COALESCE(NULLIF(referrer, ''), 'Unknown')" in query:
            counts = {}
            for click in self.clicks:
                if click["url_id"] == params[0]:
                    referrer = click["referrer"] or "Unknown"
                    counts[referrer] = counts.get(referrer, 0) + 1
            rows = [{"referrer": referrer, "clicks": count} for referrer, count in counts.items()]
            rows.sort(key=lambda row: (-row["clicks"], row["referrer"] == "Unknown", row["referrer"]))
            return Result(rows=rows)
        if query.startswith("SELECT u.id, u.short_code") or query.startswith("SELECT u.short_code"):
            user_id = params[0]
            rows = []
            for url in self.urls.values():
                if url["user_id"] == user_id:
                    total_clicks = sum(click["url_id"] == url["id"] for click in self.clicks)
                    total_impressions = sum(imp["url_id"] == url["id"] for imp in self.impressions)
                    rows.append({
                        "id": url["id"],
                        "short_code": url["short_code"],
                        "original_url": url["original_url"],
                        "total_clicks": total_clicks,
                        "total_impressions": total_impressions,
                    })
            rows.sort(key=lambda r: (-r["total_clicks"], -r["total_impressions"], r["id"]))
            return Result(rows=rows)
        raise AssertionError(f"Unhandled SQL in test double: {query}")

    def commit(self):
        pass

    def rollback(self):
        pass


@pytest.fixture
def client(monkeypatch):
    database = FakeDatabase()
    reset_custom_resolver()
    monkeypatch.setattr(auth, "get_db", lambda: database)
    monkeypatch.setattr(urls, "get_db", lambda: database)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    with app.test_client() as test_client:
        with test_client.session_transaction() as session:
            session["user_id"] = 1
        yield test_client, database
    reset_custom_resolver()


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
    assert "preview_url" in response.json
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
    assert test_client.delete(f"/api/urls/{created['id']}".replace("'", "")).status_code == 403


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
    assert overview["total_impressions"] == 0
    assert overview["ctr"] is None
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
    assert test_client.get(f"/api/urls/{first['id']}/analytics").json["total_impressions"] == 0
    assert test_client.get(f"/api/urls/{first['id']}/analytics").json["ctr"] is None
    assert test_client.get(f"/api/urls/{first['id']}/analytics/timeseries").json == []
    assert test_client.get("/api/analytics/urls/top").json == [
        {"id": first["id"], "short_code": first["short_code"], "original_url": "https://first.example", "total_clicks": 0, "total_impressions": 0, "ctr": None},
        {"id": second["id"], "short_code": second["short_code"], "original_url": "https://second.example", "total_clicks": 0, "total_impressions": 0, "ctr": None},
    ]


def test_analytics_ownership(client):
    test_client, database = client
    created = create_payload(test_client).json
    database.users[2] = {"id": 2, "username": "bob", "email": "bob@example.com"}
    database.urls[created["id"]]["user_id"] = 2
    assert test_client.get(f"/api/urls/{created['id']}/analytics").status_code == 403


# =========================================================================
# NEW CTR & IMPRESSION TESTS
# =========================================================================

def test_impression_creation_preview_and_beacon(client):
    test_client, database = client
    created = create_payload(test_client, "https://preview-target.com").json
    short_code = created["short_code"]

    # 1. Preview HTML route
    resp = test_client.get(f"/preview/{short_code}")
    assert resp.status_code == 200
    assert b"Link Preview" in resp.data
    assert b"Visit destination" in resp.data
    assert len(database.impressions) == 1
    assert database.impressions[0]["url_id"] == created["id"]

    # 2. Preview JSON format
    resp_json = test_client.get(f"/preview/{short_code}?format=json")
    assert resp_json.status_code == 200
    assert resp_json.json["destination_url"] == "https://preview-target.com"
    assert len(database.impressions) == 2

    # 3. Preview shorthand alias /p/<short_code>
    resp_p = test_client.get(f"/p/{short_code}")
    assert resp_p.status_code == 200
    assert len(database.impressions) == 3

    # 4. Tracking pixel /i/<short_code>.gif
    resp_gif = test_client.get(f"/i/{short_code}.gif")
    assert resp_gif.status_code == 200
    assert resp_gif.headers["Content-Type"] == "image/gif"
    assert resp_gif.data.startswith(b"GIF89a")
    assert len(database.impressions) == 4

    # 5. Programmatic API POST /api/urls/<short_code>/impression
    resp_api = test_client.post(f"/api/urls/{short_code}/impression")
    assert resp_api.status_code == 201
    assert resp_api.json["message"] == "Impression recorded"
    assert len(database.impressions) == 5

    # 6. Nonexistent code
    assert test_client.get("/preview/nonexistent").status_code == 404
    assert test_client.post("/api/urls/nonexistent/impression").status_code == 404


def test_ctr_calculation_and_zero_impressions(client):
    test_client, _database = client
    created = create_payload(test_client, "https://ctr-target.com").json
    url_id = created["id"]
    code = created["short_code"]

    # Direct function test for CTR
    assert urls.calculate_ctr(0, 0) is None
    assert urls.calculate_ctr(5, 0) is None
    assert urls.calculate_ctr(0, 10) == 0.0
    assert urls.calculate_ctr(1, 4) == 25.0
    assert urls.calculate_ctr(2, 4) == 50.0
    assert urls.calculate_ctr(4, 4) == 100.0

    # API overview with 0 impressions, 0 clicks
    overview0 = test_client.get(f"/api/urls/{url_id}/analytics/overview").json
    assert overview0["total_clicks"] == 0
    assert overview0["total_impressions"] == 0
    assert overview0["ctr"] is None

    # Record 4 impressions via preview
    for _ in range(4):
        test_client.get(f"/preview/{code}")

    overview_imp = test_client.get(f"/api/urls/{url_id}/analytics/overview").json
    assert overview_imp["total_impressions"] == 4
    assert overview_imp["total_clicks"] == 0
    assert overview_imp["ctr"] == 0.0

    # Record 1 click via redirect
    test_client.get(f"/{code}")

    overview_click = test_client.get(f"/api/urls/{url_id}/analytics/overview").json
    assert overview_click["total_impressions"] == 4
    assert overview_click["total_clicks"] == 1
    assert overview_click["ctr"] == 25.0

    # Record 1 more click -> 2 clicks / 4 impressions = 50.0%
    test_client.get(f"/{code}")
    overview_click2 = test_client.get(f"/api/urls/{url_id}/analytics/overview").json
    assert overview_click2["total_impressions"] == 4
    assert overview_click2["total_clicks"] == 2
    assert overview_click2["ctr"] == 50.0


def test_timeseries_and_top_urls_with_ctr(client):
    test_client, _database = client
    created = create_payload(test_client, "https://ts-target.com").json
    url_id = created["id"]
    code = created["short_code"]

    # 2 impressions and 1 click
    test_client.get(f"/preview/{code}")
    test_client.get(f"/preview/{code}")
    test_client.get(f"/{code}")

    ts = test_client.get(f"/api/urls/{url_id}/analytics/timeseries").json
    assert len(ts) == 1
    assert ts[0]["impressions"] == 2
    assert ts[0]["clicks"] == 1
    assert ts[0]["ctr"] == 50.0

    top = test_client.get("/api/analytics/urls/top").json
    matching = next(item for item in top if item["id"] == url_id)
    assert matching["total_clicks"] == 1
    assert matching["total_impressions"] == 2
    assert matching["ctr"] == 50.0

    # Batch summary endpoint
    summary = test_client.get("/api/analytics/summary").json
    summary_match = next(item for item in summary if item["id"] == url_id)
    assert summary_match["total_clicks"] == 1
    assert summary_match["total_impressions"] == 2
    assert summary_match["ctr"] == 50.0


# =========================================================================
# NEW GEOGRAPHIC ANALYTICS TESTS
# =========================================================================

def test_country_resolution_and_analytics(client):
    test_client, database = client
    created = create_payload(test_client, "https://geo-target.com").json
    url_id = created["id"]
    code = created["short_code"]

    # Impression from Germany
    test_client.get(f"/preview/{code}", headers={"CF-IPCountry": "DE"})
    # Click from Germany
    test_client.get(f"/{code}", headers={"CF-IPCountry": "DE"})

    # Click from US (via CloudFront header)
    test_client.get(f"/{code}", headers={"CloudFront-Viewer-Country": "US"})
    # Impression from US (via X-Country-Code header)
    test_client.get(f"/preview/{code}", headers={"X-Country-Code": "US"})

    assert len(database.clicks) == 2
    assert database.clicks[0]["country"] == "DE"
    assert database.clicks[1]["country"] == "US"

    assert len(database.impressions) == 2
    assert database.impressions[0]["country"] == "DE"
    assert database.impressions[1]["country"] == "US"

    countries = test_client.get(f"/api/urls/{url_id}/analytics/countries").json
    assert len(countries) == 2
    de_row = next(c for c in countries if c["country"] == "DE")
    us_row = next(c for c in countries if c["country"] == "US")
    assert de_row["clicks"] == 1
    assert de_row["impressions"] == 1
    assert de_row["ctr"] == 100.0

    assert us_row["clicks"] == 1
    assert us_row["impressions"] == 1
    assert us_row["ctr"] == 100.0


def test_geoip_private_ip_and_validation():
    # Loopback, private, and reserved IPs
    assert is_private_ip("127.0.0.1") is True
    assert is_private_ip("::1") is True
    assert is_private_ip("192.168.1.1") is True
    assert is_private_ip("10.0.0.1") is True
    assert is_private_ip("172.16.0.1") is True
    assert is_private_ip("not-an-ip") is True
    assert is_private_ip("8.8.8.8") is False
    assert is_private_ip("1.1.1.1") is False

    # Country code validation
    assert is_valid_iso_country("US") is True
    assert is_valid_iso_country("de") is True
    assert is_valid_iso_country("XX") is False  # Pseudo-code
    assert is_valid_iso_country("T1") is False  # Tor pseudo-code
    assert is_valid_iso_country("USA") is False
    assert is_valid_iso_country("") is False
    assert is_valid_iso_country(None) is False


def test_geoip_failure_and_fallback(client):
    test_client, database = client
    created = create_payload(test_client, "https://fallback.example").json
    code = created["short_code"]

    # Request with invalid/pseudo country code should not record country
    test_client.get(f"/{code}", headers={"CF-IPCountry": "XX"})
    assert database.clicks[-1]["country"] is None

    # Request with non-existent database path falls back to None without crashing
    test_client.get(f"/{code}")
    assert database.clicks[-1]["country"] is None

    # Custom resolver mock in geoip
    set_custom_resolver(lambda req, ip: "FR")
    test_client.get(f"/{code}")
    assert database.clicks[-1]["country"] == "FR"
    reset_custom_resolver()