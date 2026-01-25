# Phase 1 Review Suggestions (for Claude)

These are optimization/quality improvements for the current Phase 1 implementation.

## Scheduler & Runtime
- Avoid duplicate schedulers when Railway runs multiple processes; gate startup with an env flag or move jobs to a separate worker service. (`backend/main.py`, `backend/jobs/scheduler.py`)
- Remove the blocking initial `collect_markets_job()` call at startup or run it in the background to avoid healthcheck timeouts. (`backend/jobs/scheduler.py`)

## Logging & Security
- Do not log raw database URLs (even truncated); log only host/dbname or mask credentials. (`backend/main.py`)

## Order Book Metrics
- Fix imbalance calculation to handle `0.0` depths; use `is not None` checks instead of truthy checks. (`backend/models/orderbook.py`)
- Normalize `spread_pct` units (either fraction or percent) to avoid double-multiplying in alerts. (`backend/models/orderbook.py`, `backend/models/alert.py`)

## API Client & Performance
- Reuse a shared `httpx.AsyncClient` per job instead of creating one per request. (`backend/services/polymarket_client.py`)
- Add bounded concurrency when fetching orderbooks to reduce collection time without spiking API load. (`backend/services/polymarket_client.py`)
- Avoid N+1 `session.get()` in market sync; preload IDs or use bulk upsert. (`backend/services/polymarket_client.py`)
