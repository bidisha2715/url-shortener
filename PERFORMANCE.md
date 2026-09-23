# Performance Notes

## Query paths

The redirect lookup uses the unique constraint on `urls.short_code`. URL lists and the most-clicked query filter by `urls.user_id`. Per-URL analytics filter by `clicks.url_id`; time-series analytics also groups the matching timestamps.

## Indexes

Existing indexes in `app/schema.sql`:

- `urls.short_code` has the table's unique constraint. It supports the redirect lookup and collision checks.
- `idx_urls_user_id` supports listing URLs and filtering the most-clicked query by owner. The trade-off is additional write and storage work when URLs are inserted or their owner value changes.
- `idx_clicks_url_id` supports per-URL click analytics and the click side of URL joins.
- `idx_clicks_timestamp` supports queries that filter or order the complete click table by time. It is useful for future global time-window queries, but may not be used by every grouped per-URL query.

Stage 3 adds:

- `idx_clicks_url_timestamp ON clicks(url_id, timestamp)`: supports the common per-URL time-series access pattern by narrowing on `url_id` before reading timestamps. It adds index storage and makes click inserts slightly more expensive.

The schema uses `CREATE INDEX IF NOT EXISTS`, so running `setup_postgres.py` applies this index without changing the normalized four-table design.

## Query plans and benchmark limits

No before/after benchmark is claimed here. A valid comparison requires the same PostgreSQL version, data volume, statistics, hardware, and query parameters. To inspect a real deployment, run representative parameterized queries with PostgreSQL's `EXPLAIN (ANALYZE, BUFFERS)` after loading realistic data, for example:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT date_trunc('day', timestamp), COUNT(*)
FROM clicks
WHERE url_id = 1
GROUP BY date_trunc('day', timestamp)
ORDER BY 1;
```

Record the plan and execution time from the actual database before deciding whether another index is justified. Indexes are not automatically added for every column because they consume storage and slow writes.

On the local database during Stage 3 verification, the same query produced a `Seq Scan on clicks` followed by a sort and `GroupAggregate`. The table is currently small, so PostgreSQL reasonably chose the sequential scan. No speedup percentage is claimed, and no conclusion about production-scale performance is drawn from this small dataset.
