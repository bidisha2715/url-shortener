# Database and Analytics Queries

The active API uses PostgreSQL through `app/db.py`. The normalized tables are `users`, `urls`, `clicks`, `impressions`, and `audit_logs`. Both clicks and impressions are recorded as distinct event rows, enabling genuine, mathematically rigorous Click-Through Rate (CTR) and geographic analytics.

All user-facing URL analytics verify URL ownership prior to query execution. The aggregate queries receive the owned URL ID or logged-in user ID as parameterized arguments.

---

## Schema Overview

### 1. `impressions`
```sql
CREATE TABLE IF NOT EXISTS impressions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url_id BIGINT NOT NULL REFERENCES urls(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    device_type TEXT,
    country TEXT,
    referrer TEXT
);

CREATE INDEX IF NOT EXISTS idx_impressions_url_id ON impressions(url_id);
CREATE INDEX IF NOT EXISTS idx_impressions_timestamp ON impressions(timestamp);
CREATE INDEX IF NOT EXISTS idx_impressions_url_timestamp ON impressions(url_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_impressions_url_country ON impressions(url_id, country);
```

### 2. `clicks`
```sql
CREATE TABLE IF NOT EXISTS clicks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url_id BIGINT NOT NULL REFERENCES urls(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    device_type TEXT,
    country TEXT,
    referrer TEXT
);

CREATE INDEX IF NOT EXISTS idx_clicks_url_id ON clicks(url_id);
CREATE INDEX IF NOT EXISTS idx_clicks_timestamp ON clicks(timestamp);
CREATE INDEX IF NOT EXISTS idx_clicks_url_timestamp ON clicks(url_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_clicks_url_country ON clicks(url_id, country);
```

---

## Analytics Queries

### 1. Overview Metrics & CTR
```sql
-- Clicks totals and timestamps
SELECT COUNT(*) AS total_clicks, MIN(timestamp) AS first_click,
       MAX(timestamp) AS latest_click
FROM clicks
WHERE url_id = %s;

-- Impressions totals and timestamps
SELECT COUNT(*) AS total_impressions, MIN(timestamp) AS first_impression,
       MAX(timestamp) AS latest_impression
FROM impressions
WHERE url_id = %s;
```
* **CTR Definition:** $\text{CTR} = \left(\frac{\text{total\_clicks}}{\text{total\_impressions}}\right) \times 100$. If `total_impressions == 0`, `ctr` returns `null` (`None` in Python) to avoid division-by-zero errors.

### 2. Activity Over Time (Timeseries)
```sql
WITH click_buckets AS (
    SELECT date_trunc(%s, timestamp) AS bucket, COUNT(*) AS clicks
    FROM clicks
    WHERE url_id = %s
    GROUP BY date_trunc(%s, timestamp)
),
impression_buckets AS (
    SELECT date_trunc(%s, timestamp) AS bucket, COUNT(*) AS impressions
    FROM impressions
    WHERE url_id = %s
    GROUP BY date_trunc(%s, timestamp)
)
SELECT
    COALESCE(c.bucket, i.bucket) AS bucket,
    COALESCE(c.clicks, 0) AS clicks,
    COALESCE(i.impressions, 0) AS impressions
FROM click_buckets c
FULL OUTER JOIN impression_buckets i ON c.bucket = i.bucket
ORDER BY bucket;
```
* Supports daily (`granularity=day`) or hourly (`granularity=hour`) buckets.
* `FULL OUTER JOIN` preserves periods that received only clicks or only impressions.

### 3. Clicks by Device
```sql
SELECT COALESCE(NULLIF(device_type, ''), 'Unknown') AS device_type,
       COUNT(*) AS clicks
FROM clicks
WHERE url_id = %s
GROUP BY COALESCE(NULLIF(device_type, ''), 'Unknown')
ORDER BY clicks DESC, device_type;
```

### 4. Clicks by Referrer
```sql
SELECT COALESCE(NULLIF(referrer, ''), 'Unknown') AS referrer,
       COUNT(*) AS clicks
FROM clicks
WHERE url_id = %s
GROUP BY COALESCE(NULLIF(referrer, ''), 'Unknown')
ORDER BY clicks DESC, (COALESCE(NULLIF(referrer, ''), 'Unknown') = 'Unknown'), referrer;
```

### 5. Geographic Distribution (Clicks, Impressions, and CTR)
```sql
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
ORDER BY clicks DESC, impressions DESC, country;
```
* Groups real ISO 3166-1 alpha-2 country codes resolved from edge headers or offline GeoLite2 databases.

### 6. User Top URLs Ranking
```sql
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
ORDER BY total_clicks DESC, total_impressions DESC, u.id;
```

### 7. Consolidated Batch Summary (N+1 Elimination)
```sql
SELECT
    u.id,
    u.short_code,
    COUNT(DISTINCT c.id) AS total_clicks,
    COUNT(DISTINCT i.id) AS total_impressions
FROM urls AS u
LEFT JOIN clicks AS c ON c.url_id = u.id
LEFT JOIN impressions AS i ON i.url_id = u.id
WHERE u.user_id = %s
GROUP BY u.id, u.short_code;
```
* Powers the dashboard link counters in a single SQL query, removing the need for the React dashboard to issue separate API requests for every owned URL.
