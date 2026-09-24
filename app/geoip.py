import ipaddress
import re
from pathlib import Path

ISO_COUNTRY_REGEX = re.compile(r"^[A-Z]{2}$")
# Non-country codes sometimes emitted by Cloudflare or MaxMind
PSEUDO_COUNTRY_CODES = {"XX", "T1", "A1", "A2", "O1", "AP", "EU"}

_READER_CACHE = None
_READER_PATH = None
_CUSTOM_RESOLVER = None


def set_custom_resolver(resolver_fn):
    """Allow tests or custom runtime setups to override the country resolver."""
    global _CUSTOM_RESOLVER
    _CUSTOM_RESOLVER = resolver_fn


def reset_custom_resolver():
    global _CUSTOM_RESOLVER
    _CUSTOM_RESOLVER = None


def is_valid_iso_country(code):
    if not code or not isinstance(code, str):
        return False
    candidate = code.strip().upper()
    return bool(ISO_COUNTRY_REGEX.fullmatch(candidate)) and candidate not in PSEUDO_COUNTRY_CODES


def get_client_ip(request, trusted_proxy_count=0):
    """
    Safely extract client IP address.
    Only inspects forwarding headers if trusted_proxy_count > 0.
    """
    if trusted_proxy_count > 0:
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            candidate = cf_ip.strip()
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                pass

        if request.access_route:
            # request.access_route is parsed by Werkzeug
            candidate = request.access_route[0].strip()
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                pass

    raw_ip = (request.remote_addr or "").strip()
    try:
        ipaddress.ip_address(raw_ip)
        return raw_ip
    except ValueError:
        return "127.0.0.1"


def is_private_ip(ip_str):
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_reserved
            or ip_obj.is_link_local
            or ip_obj.is_multicast
        )
    except ValueError:
        return True


def get_geoip_reader(database_path):
    global _READER_CACHE, _READER_PATH
    if not database_path:
        return None
    if _READER_CACHE is not None and _READER_PATH == database_path:
        return _READER_CACHE

    db_file = Path(database_path)
    if not db_file.is_file():
        return None

    try:
        import geoip2.database
        _READER_CACHE = geoip2.database.Reader(str(db_file))
        _READER_PATH = database_path
        return _READER_CACHE
    except Exception:
        return None


def resolve_country_from_ip(ip_str, database_path=""):
    """
    Resolve IP to 2-letter ISO country code using local database.
    Does NOT make any synchronous external network calls.
    Returns None if IP is private, database unavailable, or lookup fails.
    """
    if not ip_str or is_private_ip(ip_str):
        return None

    reader = get_geoip_reader(database_path)
    if not reader:
        return None

    try:
        response = reader.country(ip_str)
        iso_code = response.country.iso_code
        if iso_code and is_valid_iso_country(iso_code):
            return iso_code.upper()
    except Exception:
        return None

    return None


def resolve_country(request, ip_str=None, database_path=""):
    """
    Resolve visitor country:
    1. Check custom test resolver if set
    2. Check trusted edge/CDN headers (CF-IPCountry, CloudFront-Viewer-Country, X-Country-Code)
    3. Check local GeoLite2 database if configured
    4. Fall back to None
    """
    global _CUSTOM_RESOLVER
    if _CUSTOM_RESOLVER is not None:
        try:
            custom_result = _CUSTOM_RESOLVER(request, ip_str)
            if is_valid_iso_country(custom_result):
                return custom_result.upper()
        except Exception:
            pass

    # 1. Edge/CDN headers
    for header_name in ("CF-IPCountry", "CloudFront-Viewer-Country", "X-Country-Code"):
        header_val = request.headers.get(header_name)
        if header_val and is_valid_iso_country(header_val):
            return header_val.strip().upper()

    # 2. Local GeoIP database
    if not ip_str:
        ip_str = get_client_ip(request)

    return resolve_country_from_ip(ip_str, database_path=database_path)
