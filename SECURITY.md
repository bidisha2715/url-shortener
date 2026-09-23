# Security and Privacy Notes

- URL and analytics endpoints require the Flask session and verify the URL owner before returning analytics.
- Passwords are hashed by Werkzeug. The Flask secret and PostgreSQL connection string are loaded from environment variables; `.env` is ignored by Git and must never be committed.
- Redirects store the request IP in PostgreSQL for potential operational analysis. Raw IP addresses are not returned by any public analytics endpoint. Production deployments should define a retention or anonymization policy and restrict database access.
- Device categories are a best-effort classification of the User-Agent header: `Desktop`, `Mobile`, `Tablet`, or `Unknown`. User-Agent values are not proof of identity or exact hardware.
- Referrers come only from the request `Referer` header and may be absent, reduced, or controlled by the client.
- Country is nullable. No geolocation provider is configured, so the country endpoint returns only existing non-null database values, normally an empty array.
- CTR is intentionally unavailable. The application records clicks but has no legitimate impressions event, so reporting clicks divided by an invented denominator would be misleading.
- Cookie security settings are configurable with `SESSION_COOKIE_SECURE`. Use `true` behind HTTPS in production.
