import re
import secrets
import string
from urllib.parse import urlparse

from flask import Blueprint, jsonify, redirect, request
from psycopg.errors import UniqueViolation

from .auth import current_user, login_required
from .db import get_db


urls = Blueprint("urls", __name__)
ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,50}$")
CODE_ALPHABET = string.ascii_letters + string.digits


def generate_short_code(length=6):
    """Generate a readable code; the database remains the uniqueness authority."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def is_valid_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_alias(alias):
    if alias is None:
        return None
    if not isinstance(alias, str) or not ALIAS_PATTERN.fullmatch(alias):
        raise ValueError("custom_alias must be 3-50 letters, numbers, '_' or '-'")
    return alias


def serialize_url(row):
    result = dict(row)
    for field in ("created_at", "updated_at"):
        if result.get(field) is not None:
            result[field] = result[field].isoformat()
    result["short_url"] = request.host_url.rstrip("/") + "/" + result["short_code"]
    return result


def error(message, status):
    return jsonify({"error": message}), status


def find_owned_url(url_id):
    user = current_user()
    row = get_db().execute(
        """
        SELECT id, user_id, original_url, short_code, custom_alias, created_at, updated_at
        FROM urls
        WHERE id = %s
        """,
        (url_id,),
    ).fetchone()
    if row is None:
        return None, error("URL not found", 404)
    if row["user_id"] != user["id"]:
        return None, error("You do not have access to this URL", 403)
    return row, None


@urls.post("/api/urls")
@login_required
def create_url():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return error("JSON object required", 400)

    original_url = data.get("original_url")
    if not is_valid_url(original_url):
        return error("original_url must be a valid http or https URL", 400)

    try:
        custom_alias = validate_alias(data.get("custom_alias"))
    except ValueError as exc:
        return error(str(exc), 400)

    connection = get_db()
    user_id = current_user()["id"]
    if custom_alias:
        existing = connection.execute(
            "SELECT id FROM urls WHERE short_code = %s OR custom_alias = %s",
            (custom_alias, custom_alias),
        ).fetchone()
        if existing:
            return error("Custom alias already exists", 409)

    for _attempt in range(10):
        short_code = custom_alias or generate_short_code()
        try:
            row = connection.execute(
                """
                INSERT INTO urls (user_id, original_url, short_code, custom_alias)
                VALUES (%s, %s, %s, %s)
                RETURNING id, user_id, original_url, short_code, custom_alias,
                          created_at, updated_at
                """,
                (user_id, original_url.strip(), short_code, custom_alias),
            ).fetchone()
            connection.commit()
            return jsonify(serialize_url(row)), 201
        except UniqueViolation:
            connection.rollback()
            if custom_alias:
                return error("Custom alias already exists", 409)

    return error("Could not generate a unique short code", 500)


@urls.get("/api/urls")
@login_required
def list_urls():
    user_id = current_user()["id"]
    rows = get_db().execute(
        """
        SELECT id, user_id, original_url, short_code, custom_alias, created_at, updated_at
        FROM urls
        WHERE user_id = %s
        ORDER BY created_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    return jsonify([serialize_url(row) for row in rows])


@urls.get("/api/urls/<int:url_id>")
@login_required
def get_url(url_id):
    row, response = find_owned_url(url_id)
    if response:
        return response
    return jsonify(serialize_url(row))


@urls.put("/api/urls/<int:url_id>")
@login_required
def update_url(url_id):
    row, response = find_owned_url(url_id)
    if response:
        return response

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return error("JSON object required", 400)
    if "original_url" not in data and "custom_alias" not in data:
        return error("Provide original_url or custom_alias", 400)

    original_url = data.get("original_url", row["original_url"])
    if not is_valid_url(original_url):
        return error("original_url must be a valid http or https URL", 400)

    custom_alias = row["custom_alias"]
    if "custom_alias" in data:
        try:
            custom_alias = validate_alias(data["custom_alias"])
        except ValueError as exc:
            return error(str(exc), 400)
        if custom_alias is None:
            return error("custom_alias cannot be cleared", 400)

    short_code = custom_alias or row["short_code"]
    connection = get_db()
    try:
        updated = connection.execute(
            """
            UPDATE urls
            SET original_url = %s, short_code = %s, custom_alias = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
            RETURNING id, user_id, original_url, short_code, custom_alias,
                      created_at, updated_at
            """,
            (original_url.strip(), short_code, custom_alias, row["id"], current_user()["id"]),
        ).fetchone()
        connection.commit()
    except UniqueViolation:
        connection.rollback()
        return error("Custom alias already exists", 409)
    return jsonify(serialize_url(updated))


@urls.delete("/api/urls/<int:url_id>")
@login_required
def delete_url(url_id):
    row, response = find_owned_url(url_id)
    if response:
        return response

    connection = get_db()
    connection.execute(
        "DELETE FROM urls WHERE id = %s AND user_id = %s",
        (row["id"], current_user()["id"]),
    )
    connection.commit()
    return jsonify({"message": "URL deleted"})


@urls.get("/<short_code>")
def redirect_short_url(short_code):
    connection = get_db()
    row = connection.execute(
        "SELECT id, original_url FROM urls WHERE short_code = %s",
        (short_code,),
    ).fetchone()
    if row is None:
        return error("Short URL not found", 404)

    connection.execute("INSERT INTO clicks (url_id) VALUES (%s)", (row["id"],))
    connection.commit()
    return redirect(row["original_url"])