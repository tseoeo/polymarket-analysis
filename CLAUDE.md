# Project Context for Claude

## Deployment

- **Railway** is connected to GitHub - pushing to `main` triggers automatic deployment
- No need to run `railway up` manually; just `git push` to deploy

## Project Structure

- `backend/` - Python FastAPI backend
  - `services/` - Business logic (polymarket_client, analyzers)
  - `models/` - SQLAlchemy models (Market, Trade, OrderBookSnapshot, Alert)
  - `jobs/scheduler.py` - APScheduler background jobs
  - `tests/` - pytest test suite

## Key Configuration

- `ENABLE_SCHEDULER=true` - Set on ONE worker only to run background jobs
- Analysis job runs hourly, trade collection every 5min, orderbook/market sync every 15min

## Testing

```bash
cd backend && source venv/bin/activate && pytest -v
```

## Current Phase

Phase 3 complete - Analysis engine with:
- VolumeAnalyzer (3x spike threshold)
- SpreadAnalyzer (5% threshold)
- MarketMakerAnalyzer (50% depth drop)
- ArbitrageDetector (2% min profit, orderbook-first with market price fallback)
