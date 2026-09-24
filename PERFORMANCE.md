# Performance Notes

## Query Paths

1. **Redirect Path (`/<short_code>`):** Uses the unique B-tree index on `urls.short_code` to look up the destination in $O(\log N)$ time. Inserts a click record into `clicks` with resolved country, client IP, device, and referrer.
2. **Preview & Impression Path (`/preview/<short_code>`, `/i/<short_code>.gif`):** Looks up URL by `short_code` and writes an event row to `impressions`.
3. **Per-URL Analytics:** Filtered by `url_id` using indexes on `clicks` and `impressions`. Time-series queries group by `date_trunc` buckets.
4. **Dashboard Listing & Batch Summary:** Uses `GET /api/analytics/summary` to aggregate total clicks and impressions for all owned URLs in a single query, eliminating the previous $N+1$ per-URL query bottleneck.

---

## Indexes in `app/schema.sql`

* **`urls.short_code` (Unique):** Supports instantaneous redirect and preview resolution as well as alias collision checks.
* **`idx_urls_user_id`:** Speeds up user URL listings and ownership filters.
* **`idx_clicks_url_id` & `idx_impressions_url_id`:** Enables rapid filtering of events belonging to a specific URL.
* **`idx_clicks_url_timestamp` & `idx_impressions_url_timestamp`:** Composite index optimizing time-series aggregation by filtering on `url_id` and grouping by `timestamp`.
* **`idx_clicks_url_country` & `idx_impressions_url_country`:** Composite index accelerating geographic aggregations by filtering on `url_id` and grouping on `country`.

---

## GeoIP Resolution Performance

* **Zero External HTTP Latency:** No third-party HTTP requests are made synchronously during redirects. Lookups are executed in sub-millisecond time:
  1. Header inspection (e.g. `CF-IPCountry`, `CloudFront-Viewer-Country`) reads directly from memory ($O(1)$).
  2. Local binary database lookups (MaxMind GeoLite2 `.mmdb`) use a memory-mapped binary tree search without network hops.
* **Failure Resistance:** If the GeoIP database is missing, corrupted, or lookup fails, the redirect handler catches the error, sets country to `NULL`, and completes the redirect without degrading user experience.

---

## Write Throughput and Scaling Considerations

* **Impression Volume:** In high-traffic deployments, impressions can occur at orders of magnitude higher volume than clicks.
* **Write Costs:** Each additional index on `impressions` slightly increases insert latency. The four indexes chosen (`url_id`, `timestamp`, `url_timestamp`, `url_country`) balance read performance for dashboard visualizations with insert speed.
* **Future Optimizations:** For massive web-scale deployments, consider buffered write queues (e.g., Redis or Kafka) or PostgreSQL table partitioning by month for `clicks` and `impressions`.
