# Security and Privacy Notes

- **Authentication & Sessions:** User passwords are encrypted using Werkzeug's secure hash algorithms (`scrypt` / `pbkdf2:sha256`). Sessions are stored in signed, HTTP-only cookies (`SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = 'Lax'`). In production behind HTTPS, `SESSION_COOKIE_SECURE = true` must be enabled.
- **Ownership Authorization:** All CRUD and analytics endpoints enforce strict user ownership. A user cannot view, edit, or analyze URLs belonging to another account.
- **Client IP & Reverse Proxy Security:** Client IP resolution is protected against header spoofing:
  - If `TRUSTED_PROXY_COUNT == 0` (default), only the direct socket address (`request.remote_addr`) is trusted. Arbitrary `X-Forwarded-For` headers sent by clients are discarded.
  - If `TRUSTED_PROXY_COUNT > 0`, Werkzeug's `ProxyFix` middleware safely strips untrusted hops before reading the client IP.
- **Privacy & Anonymity:**
  - Raw visitor IP addresses are stored privately in PostgreSQL solely for audit and security analysis.
  - **No analytics API ever returns raw IP addresses.**
  - Geolocation is aggregated strictly at the country code level (ISO 3166-1 alpha-2).
- **Zero Third-Party Data Leakage:**
  - GeoIP lookups are performed entirely locally or via edge CDN headers.
  - No external third-party API is called during user redirects or impression logging, preventing third-party tracking of visitor traffic.
- **Zero-Division and Denial of Service Protection:**
  - CTR calculations explicitly check for zero impressions and return `null` rather than generating `ZeroDivisionError` or returning NaN/Infinity.
  - Database queries are strictly parameterized using `psycopg`, preventing SQL injection.
