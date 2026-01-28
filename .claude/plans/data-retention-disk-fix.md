# Problem: Railway Postgres Out of Disk Space

## The Crash

PostgreSQL on Railway ran out of disk space:
```
FATAL: could not write to file "pg_wal/xlogtemp.29": No space left on device
```

The database could not complete WAL recovery and shut down.

## Root Cause

We collect data aggressively but the current 30-day retention is too much for our Railway volume size. The two biggest tables are:

| Table | Collection Rate | Est. Rows/Day | Why It's Big |
|-------|----------------|---------------|--------------|
| `trades` | Every 5 min, all active markets | Thousands+ | Raw trade records with price, size, side, timestamp |
| `orderbook_snapshots` | Every 15 min, all active markets | ~96 per market | JSON arrays of full bid/ask books |

`orderbook_snapshots` is likely the worst offender -- each row stores full `bids` and `asks` JSON arrays.

## What Data Do We Actually Need?

### Can aggressively prune (7-day retention is sufficient):

- **`trades`** -- VolumeAnalyzer's longest lookback is 7 days (baseline). After that, `volume_stats` has the aggregated data. **Reduce from 30 to 7 days.**
- **`orderbook_snapshots`** -- OrderbookAnalyzer's longest lookback is 7 days (best-hours). SpreadAnalyzer only needs 30-min-old data. **Reduce from 30 to 7 days.**

### Can prune moderately:

- **`alerts`** (dismissed/expired) -- Only active alerts matter. Dismissed alerts older than 7 days have no use. **Reduce from 30 to 7 days.**

### Must keep forever (small tables, reference data):

- **`markets`** -- Reference data, foreign keys everywhere
- **`market_relationships`** -- Cross-market arbitrage config
- **`volume_stats`** -- Already aggregated summaries, small
- **`job_runs`** -- Observability (but could prune after 30 days if needed)
- **`watchlist_items`** -- User data

## Proposed Fix

### 1. Reduce `data_retention_days` from 30 to 7

In `backend/config.py`, change:
```python
data_retention_days: int = 7  # was 30
```

This affects the existing `cleanup_old_data` job which already deletes old trades, snapshots, and dismissed alerts.

### 2. Run an immediate one-time cleanup

Add a migration or management command that:
```sql
DELETE FROM orderbook_snapshots WHERE timestamp < NOW() - INTERVAL '7 days';
DELETE FROM trades WHERE timestamp < NOW() - INTERVAL '7 days';
DELETE FROM alerts WHERE dismissed_at IS NOT NULL AND dismissed_at < NOW() - INTERVAL '7 days';
VACUUM FULL;  -- reclaim disk space
```

**Important:** `VACUUM FULL` is needed to actually return disk space to the OS. Regular `VACUUM` only marks space as reusable by Postgres but doesn't shrink the files.

### 3. Add VACUUM to the cleanup job

After the daily `cleanup_old_data` deletes rows, run `VACUUM` (not FULL -- that locks tables) to keep space tidy going forward.

### 4. Consider adding row count limits as a safety net

In case data grows unexpectedly, add a max row count per table (e.g., keep at most 500k trades, 100k snapshots) as a secondary retention mechanism.

## Immediate Recovery

Before any code changes, the Railway Postgres volume needs space freed:
1. **Option A:** Increase Railway volume size in the dashboard (quick fix)
2. **Option B:** Connect via `railway connect postgres` and run the DELETE + VACUUM FULL commands above
3. Then deploy the retention config change to prevent recurrence

## Files to Change

- `backend/config.py` -- `data_retention_days: int = 7`
- `backend/jobs/scheduler.py` -- Add VACUUM after cleanup, optionally add row-count safety net
- Optionally: add a one-time migration script for the initial purge

---

# Codex Recommendations (for Claude to implement)

## ✅ Safe Defaults (recommended)

1) **Reduce retention to 7 days**
   - Change `data_retention_days` from 30 → 7.
   - File: `backend/config.py`

2) **Add an index on `alerts.dismissed_at`**
   - Cleanup deletes by `dismissed_at < cutoff`; without an index this will scan.
   - File: `backend/models/alert.py` → set `dismissed_at` to `index=True`.

3) **Add `VACUUM (ANALYZE)` after cleanup (NOT FULL)**
   - `VACUUM` must run **outside** a transaction in Postgres.
   - Use a separate autocommit connection after the delete/commit.
   - File: `backend/jobs/scheduler.py`
   - Pattern (async SQLAlchemy):
     - After `session.commit()`, do:
       - `async with engine.connect() as conn:`
       - `await conn.execution_options(isolation_level="AUTOCOMMIT").execute(text("VACUUM (ANALYZE)"))`

## ⚠ Immediate Recovery Guidance (one-time ops)

If Railway is already out of disk:
- **Prefer increasing volume size first** (fastest unblock).
- Then delete in **batches** to avoid large WAL + long locks:
  - Example: delete 1 day at a time until <7 days remain.
- Run **manual `VACUUM (ANALYZE)`**, and only use **`VACUUM FULL`** off-peak if disk needs to shrink (it locks tables and can fail if disk is already full).

## Optional Safety Net

Add a max row count cap per table (after retention delete), e.g.:
- `trades` max 500k rows
- `orderbook_snapshots` max 100k rows

Only apply if disk keeps growing unexpectedly.
