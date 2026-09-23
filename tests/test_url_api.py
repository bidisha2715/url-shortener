from datetime import datetime, timezone

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
            self.clicks.append({"url_id": params[0]})
            return Result()
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
    assert database.clicks == [{"url_id": created["id"]}]