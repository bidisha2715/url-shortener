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
    result["preview_url"] = request.host_url.rstrip("/") + "/preview/" + result["short_code"]
    return result


def calculate_ctr(clicks, impressions):
    """
    Calculate Click-Through Rate (CTR) percentage:
    CTR = clicks / impressions * 100
    If impressions is 0, return None consistently to prevent division by zero.
    """
    if not impressions or impressions <= 0:
        return None
    return round((clicks / impressions) * 100, 2)


def extract_request_metadata():
    from flask import current_app
    from .geoip import get_client_ip, resolve_country

    trusted_proxy_count = current_app.config.get("TRUSTED_PROXY_COUNT", 0)
    geoip_db_path = current_app.config.get("GEOIP_DATABASE_PATH", "")

    ip_addr = get_client_ip(request, trusted_proxy_count)
    device = detect_device_type(request.user_agent.string)
    country = resolve_country(request, ip_str=ip_addr, database_path=geoip_db_path)
    referrer = request.referrer or None
    return ip_addr, device, country, referrer


def record_impression(url_id):
    ip_addr, device, country, referrer = extract_request_metadata()
    connection = get_db()
    connection.execute(
        """
        INSERT INTO impressions (url_id, ip_address, device_type, country, referrer)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (url_id, ip_addr, device, country, referrer),
    )
    connection.commit()



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
    click_totals = connection.execute(
        """
        SELECT COUNT(*) AS total_clicks, MIN(timestamp) AS first_click,
               MAX(timestamp) AS latest_click
        FROM clicks
        WHERE url_id = %s
        """,
        (url_id,),
    ).fetchone()

    impression_totals = connection.execute(
        """
        SELECT COUNT(*) AS total_impressions, MIN(timestamp) AS first_impression,
               MAX(timestamp) AS latest_impression
        FROM impressions
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

    total_clicks = click_totals["total_clicks"] if click_totals else 0
    total_impressions = impression_totals["total_impressions"] if impression_totals else 0
    ctr = calculate_ctr(total_clicks, total_impressions)

    return {
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "ctr": ctr,
        "first_click": serialize_timestamp(click_totals["first_click"] if click_totals else None),
        "latest_click": serialize_timestamp(click_totals["latest_click"] if click_totals else None),
        "first_impression": serialize_timestamp(impression_totals["first_impression"] if impression_totals else None),
        "latest_impression": serialize_timestamp(impression_totals["latest_impression"] if impression_totals else None),
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
        WITH click_buckets AS (
            SELECT date_trunc('{bucket}', timestamp) AS bucket, COUNT(*) AS clicks
            FROM clicks
            WHERE url_id = %s
            GROUP BY date_trunc('{bucket}', timestamp)
        ),
        impression_buckets AS (
            SELECT date_trunc('{bucket}', timestamp) AS bucket, COUNT(*) AS impressions
            FROM impressions
            WHERE url_id = %s
            GROUP BY date_trunc('{bucket}', timestamp)
        )
        SELECT
            COALESCE(c.bucket, i.bucket) AS bucket,
            COALESCE(c.clicks, 0) AS clicks,
            COALESCE(i.impressions, 0) AS impressions
        FROM click_buckets c
        FULL OUTER JOIN impression_buckets i ON c.bucket = i.bucket
        ORDER BY bucket
        """,
        (url_id, url_id),
    ).fetchall()

    return jsonify([
        {
            "date": serialize_timestamp(row["bucket"]),
            "clicks": row["clicks"],
            "impressions": row["impressions"],
            "ctr": calculate_ctr(row["clicks"], row["impressions"]),
        }
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
        """,
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
        WITH click_countries AS (
            SELECT country, COUNT(*) AS clicks
            FROM clicks
            WHERE url_id = %s AND country IS NOT NULL AND NULLIF(country, '') IS NOT NULL
            GROUP BY country
        ),
        impression_countries AS (
            SELECT country, COUNT(*) AS impressions
            FROM impressions
            WHERE url_id = %s AND country IS NOT NULL AND NULLIF(country, '') IS NOT NULL
            GROUP BY country
        )
        SELECT
            COALESCE(c.country, i.country) AS country,
            COALESCE(c.clicks, 0) AS clicks,
            COALESCE(i.impressions, 0) AS impressions
        FROM click_countries c
        FULL OUTER JOIN impression_countries i ON c.country = i.country
        ORDER BY clicks DESC, impressions DESC, country
        """,
        (url_id, url_id),
    ).fetchall()
    return jsonify([
        {
            "country": row["country"],
            "clicks": row["clicks"],
            "impressions": row["impressions"],
            "ctr": calculate_ctr(row["clicks"], row["impressions"]),
        }
        for row in rows
    ])


@urls.get("/api/analytics/urls/top")
@login_required
def most_clicked_urls():
    rows = get_db().execute(
        """
        SELECT
            u.id,
            u.short_code,
            u.original_url,
            COUNT(DISTINCT c.id) AS total_clicks,
            COUNT(DISTINCT i.id) AS total_impressions
        FROM urls AS u
        LEFT JOIN clicks AS c ON c.url_id = u.id
        LEFT JOIN impressions AS i ON i.url_id = u.id
        WHERE u.user_id = %s
        GROUP BY u.id, u.short_code, u.original_url
        ORDER BY total_clicks DESC, total_impressions DESC, u.id
        """,
        (current_user()["id"],),
    ).fetchall()
    return jsonify([
        {
            "id": row["id"],
            "short_code": row["short_code"],
            "original_url": row["original_url"],
            "total_clicks": row["total_clicks"],
            "total_impressions": row["total_impressions"],
            "ctr": calculate_ctr(row["total_clicks"], row["total_impressions"]),
        }
        for row in rows
    ])


@urls.get("/api/analytics/summary")
@login_required
def analytics_summary():
    """Consolidated URL stats to eliminate frontend N+1 queries."""
    rows = get_db().execute(
        """
        SELECT
            u.id,
            u.short_code,
            COUNT(DISTINCT c.id) AS total_clicks,
            COUNT(DISTINCT i.id) AS total_impressions
        FROM urls AS u
        LEFT JOIN clicks AS c ON c.url_id = u.id
        LEFT JOIN impressions AS i ON i.url_id = u.id
        WHERE u.user_id = %s
        GROUP BY u.id, u.short_code
        """,
        (current_user()["id"],),
    ).fetchall()
    return jsonify([
        {
            "id": row["id"],
            "short_code": row["short_code"],
            "total_clicks": row["total_clicks"],
            "total_impressions": row["total_impressions"],
            "ctr": calculate_ctr(row["total_clicks"], row["total_impressions"]),
        }
        for row in rows
    ])


@urls.get("/preview/<short_code>")
@urls.get("/p/<short_code>")
def preview_url(short_code):
    connection = get_db()
    row = connection.execute(
        "SELECT id, original_url, short_code FROM urls WHERE short_code = %s",
        (short_code,),
    ).fetchone()
    if row is None:
        return error("Short URL not found", 404)

    record_impression(row["id"])

    if request.accept_mimetypes.best_match(["application/json", "text/html"]) == "application/json" or request.args.get("format") == "json":
        return jsonify({
            "id": row["id"],
            "short_code": row["short_code"],
            "original_url": row["original_url"],
            "destination_url": row["original_url"],
            "short_url": request.host_url.rstrip("/") + "/" + row["short_code"],
            "preview_url": request.host_url.rstrip("/") + "/preview/" + row["short_code"],
        })

    from markupsafe import escape
    dest_url = escape(row["original_url"])
    code = escape(row["short_code"])
    redirect_target = request.host_url.rstrip("/") + "/" + str(code)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Link Preview - {code}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f1eee6;
            color: #24312d;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 1.5rem;
            box-sizing: border-box;
        }}
        .preview-card {{
            background: #fffaf1;
            border: 1px solid #c9d1c5;
            border-radius: 6px;
            max-width: 540px;
            width: 100%;
            padding: 2rem;
            box-shadow: 0 4px 16px rgba(0,0,0,0.06);
        }}
        .eyebrow {{
            color: #d26945;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 0.75rem;
        }}
        h1 {{
            font-size: 1.6rem;
            margin: 0 0 1rem;
            word-break: break-word;
        }}
        .destination-box {{
            background: #faf8f2;
            border: 1px solid #b9c7ba;
            padding: 0.85rem;
            border-radius: 4px;
            word-break: break-all;
            color: #3e5e49;
            font-size: 0.92rem;
            margin: 1.25rem 0;
        }}
        .btn-visit {{
            display: inline-block;
            background: #d26945;
            color: #fffaf1;
            text-decoration: none;
            padding: 0.85rem 1.4rem;
            font-weight: 700;
            font-size: 0.95rem;
            border-radius: 4px;
            transition: background 0.2s;
        }}
        .btn-visit:hover {{
            background: #b85433;
        }}
        .meta {{
            margin-top: 1.5rem;
            font-size: 0.78rem;
            color: #8a958b;
        }}
    </style>
</head>
<body>
    <div class="preview-card">
        <div class="eyebrow">Link Preview</div>
        <h1>You are about to visit:</h1>
        <div class="destination-box">{dest_url}</div>
        <a class="btn-visit" href="{redirect_target}">Visit destination &rarr;</a>
        <div class="meta">Viewing this preview records an impression. Clicking "Visit destination" proceeds to the site and records a click.</div>
    </div>
</body>
</html>"""
    return html_content, 200, {"Content-Type": "text/html; charset=utf-8"}


PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
    b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


@urls.get("/i/<short_code>.gif")
def impression_pixel(short_code):
    connection = get_db()
    row = connection.execute(
        "SELECT id FROM urls WHERE short_code = %s",
        (short_code,),
    ).fetchone()
    if row:
        record_impression(row["id"])
    return PIXEL_GIF, 200, {
        "Content-Type": "image/gif",
        "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }


@urls.post("/api/urls/<short_code>/impression")
def api_record_impression(short_code):
    connection = get_db()
    row = connection.execute(
        "SELECT id FROM urls WHERE short_code = %s",
        (short_code,),
    ).fetchone()
    if row is None:
        return error("Short URL not found", 404)
    record_impression(row["id"])
    return jsonify({"message": "Impression recorded", "short_code": short_code}), 201


@urls.get("/<short_code>")
def redirect_short_url(short_code):
    connection = get_db()
    row = connection.execute(
        "SELECT id, original_url FROM urls WHERE short_code = %s",
        (short_code,),
    ).fetchone()
    if row is None:
        return error("Short URL not found", 404)

    ip_addr, device, country, referrer = extract_request_metadata()

    connection.execute(
        """
        INSERT INTO clicks (url_id, ip_address, device_type, country, referrer)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (row["id"], ip_addr, device, country, referrer),
    )
    connection.commit()
    return redirect(row["original_url"])
