# Project Context for Claude

## Deployment

- **Railway** is connected to GitHub - pushing to `main` triggers automatic deployment
- No need to run `railway up` manually; just `git push` to deploy
- **Production URL:** https://polymarket-analysis-production.up.railway.app

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

Phase 4 complete - API endpoints:
- `GET /api/alerts` - List with filters
- `GET /api/alerts/{id}` - Detail
- `PATCH /api/alerts/{id}/dismiss` - Dismiss
- `GET /api/markets` - List with alert counts
- `GET /api/markets/{id}` - Detail
- `GET /api/markets/{id}/alerts` - Market alerts

Phase 3 complete - Analysis engine with:
- VolumeAnalyzer (3x spike threshold)
- SpreadAnalyzer (5% threshold)
- MarketMakerAnalyzer (50% depth drop)
- ArbitrageDetector (2% min profit, orderbook-first with market price fallback)

---

## Coordination with Codex

Read `AGENTS.md` for the coordination protocol.
You are the **builder** and the only one who moves registry items.

Quick reference:
1. Read `.claude/REGISTRY.md` and `.claude/ISSUES.md`
2. Pick or create a Queue item (Q-###)
3. Move to In Progress (W-###) when starting
4. Move to Done (D-###) when finished
5. Log any issues you find in `.claude/ISSUES.md`
