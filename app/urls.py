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


def detect_device_type(user_agent):
    """Classify common user-agent signals without pretending to identify a device exactly."""
    value = (user_agent or "").lower()
    if not value:
        return "Unknown"
    if any(token in value for token in ("tablet", "ipad", "kindle", "silk")):
        return "Tablet"
    if any(token in value for token in ("mobile", "iphone", "ipod", "android", "blackberry", "opera mini")):
        return "Mobile"
    return "Desktop"


def serialize_timestamp(value):
    return value.isoformat() if value is not None else None


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


def owned_url_or_error(url_id):
    row, response = find_owned_url(url_id)
    if response:
        return None, response
    return row, None


def overview_data(url_id):
    connection = get_db()
    totals = connection.execute(
        """
        SELECT COUNT(*) AS total_clicks, MIN(timestamp) AS first_click,
               MAX(timestamp) AS latest_click
        FROM clicks
        WHERE url_id = %s
        """,
        (url_id,),
    ).fetchone()
    device = connection.execute(
        """
        SELECT COALESCE(NULLIF(device_type, ''), 'Unknown') AS device_type,
               COUNT(*) AS clicks
        FROM clicks
        WHERE url_id = %s
        GROUP BY COALESCE(NULLIF(device_type, ''), 'Unknown')
        ORDER BY clicks DESC, device_type
        LIMIT 1
        """,
        (url_id,),
    ).fetchone()
    referrer = connection.execute(
        """
        SELECT referrer, COUNT(*) AS clicks
        FROM clicks
        WHERE url_id = %s AND referrer IS NOT NULL AND NULLIF(referrer, '') IS NOT NULL
        GROUP BY referrer
        ORDER BY clicks DESC, (referrer = 'Unknown'), referrer
        LIMIT 1
        """,
        (url_id,),
    ).fetchone()
    return {
        "total_clicks": totals["total_clicks"],
        "first_click": serialize_timestamp(totals["first_click"]),
        "latest_click": serialize_timestamp(totals["latest_click"]),
        "most_common_device_type": device["device_type"] if device else None,
        "most_common_referrer": referrer["referrer"] if referrer else None,
    }


@urls.get("/api/urls/<int:url_id>/analytics")
@login_required
def analytics(url_id):
    _row, response = owned_url_or_error(url_id)
    if response:
        return response
    return jsonify(overview_data(url_id))


@urls.get("/api/urls/<int:url_id>/analytics/overview")
@login_required
def analytics_overview(url_id):
    _row, response = owned_url_or_error(url_id)
    if response:
        return response
    return jsonify(overview_data(url_id))


@urls.get("/api/urls/<int:url_id>/analytics/timeseries")
@login_required
def analytics_timeseries(url_id):
    _row, response = owned_url_or_error(url_id)
    if response:
        return response
    granularity = request.args.get("granularity", "day")
    if granularity not in {"day", "hour"}:
        return error("granularity must be day or hour", 400)
    bucket = "day" if granularity == "day" else "hour"
    rows = get_db().execute(
        f"""
        SELECT date_trunc('{bucket}', timestamp) AS bucket, COUNT(*) AS clicks
        FROM clicks
        WHERE url_id = %s
        GROUP BY date_trunc('{bucket}', timestamp)
        ORDER BY bucket
        """,
        (url_id,),
    ).fetchall()
    return jsonify([
        {"date": serialize_timestamp(row["bucket"]), "clicks": row["clicks"]}
        for row in rows
    ])


@urls.get("/api/urls/<int:url_id>/analytics/devices")
@login_required
def analytics_devices(url_id):
    _row, response = owned_url_or_error(url_id)
    if response:
        return response
    rows = get_db().execute(
        """
        SELECT COALESCE(NULLIF(device_type, ''), 'Unknown') AS device_type,
               COUNT(*) AS clicks
        FROM clicks
        WHERE url_id = %s
        GROUP BY COALESCE(NULLIF(device_type, ''), 'Unknown')
        ORDER BY clicks DESC, device_type
        """,
        (url_id,),
    ).fetchall()
    return jsonify([dict(row) for row in rows])


@urls.get("/api/urls/<int:url_id>/analytics/referrers")
@login_required
def analytics_referrers(url_id):
    _row, response = owned_url_or_error(url_id)
    if response:
        return response
    rows = get_db().execute(
        """
        SELECT COALESCE(NULLIF(referrer, ''), 'Unknown') AS referrer,
               COUNT(*) AS clicks
        FROM clicks
        WHERE url_id = %s
        GROUP BY COALESCE(NULLIF(referrer, ''), 'Unknown')
        ORDER BY clicks DESC, (COALESCE(NULLIF(referrer, ''), 'Unknown') = 'Unknown'), referrer
        """
        ,
        (url_id,),
    ).fetchall()
    return jsonify([dict(row) for row in rows])


@urls.get("/api/urls/<int:url_id>/analytics/countries")
@login_required
def analytics_countries(url_id):
    _row, response = owned_url_or_error(url_id)
    if response:
        return response
    rows = get_db().execute(
        """
        SELECT country, COUNT(*) AS clicks
        FROM clicks
        WHERE url_id = %s AND country IS NOT NULL AND NULLIF(country, '') IS NOT NULL
        GROUP BY country
        ORDER BY clicks DESC, country
        """,
        (url_id,),
    ).fetchall()
    return jsonify([dict(row) for row in rows])


@urls.get("/api/analytics/urls/top")
@login_required
def most_clicked_urls():
    rows = get_db().execute(
        """
        SELECT u.short_code, u.original_url, COUNT(c.id) AS total_clicks
        FROM urls AS u
        LEFT JOIN clicks AS c ON c.url_id = u.id
        WHERE u.user_id = %s
        GROUP BY u.id, u.short_code, u.original_url
        ORDER BY total_clicks DESC, u.id
        """,
        (current_user()["id"],),
    ).fetchall()
    return jsonify([dict(row) for row in rows])


@urls.get("/<short_code>")
def redirect_short_url(short_code):
    connection = get_db()
    row = connection.execute(
        "SELECT id, original_url FROM urls WHERE short_code = %s",
        (short_code,),
    ).fetchone()
    if row is None:
        return error("Short URL not found", 404)

    connection.execute(
        """
        INSERT INTO clicks (url_id, ip_address, device_type, referrer)
        VALUES (%s, %s, %s, %s)
        """,
        (row["id"], request.remote_addr, detect_device_type(request.user_agent.string), request.referrer or None),
    )
    connection.commit()
    return redirect(row["original_url"])