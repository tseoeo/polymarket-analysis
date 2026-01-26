# Project Context for Claude

## Deployment

- **Railway** is connected to GitHub - pushing to `main` triggers automatic deployment
- No need to run `railway up` manually; just `git push` to deploy
- **Production URL:** https://polymarket-analysis-production.up.railway.app

## Project Structure

- `backend/` - Python FastAPI backend
  - `services/` - Business logic (polymarket_client, analyzers)
    - `volume_analyzer.py` - Volume spike detection, 7-day baseline, acceleration
    - `spread_analyzer.py` - Spread monitoring and alerts
    - `mm_analyzer.py` - Market maker detection and pullback alerts
    - `arbitrage_detector.py` - Single-market Yes/No arbitrage
    - `orderbook_analyzer.py` - Slippage calculation, spread patterns
    - `relationship_detector.py` - Cross-market relationship detection
    - `cross_market_arbitrage.py` - Cross-market arbitrage detection
  - `models/` - SQLAlchemy models
    - `market.py` - Market model
    - `trade.py` - Trade model
    - `orderbook.py` - OrderBookSnapshot model
    - `alert.py` - Alert model
    - `job_run.py` - JobRun model
    - `relationship.py` - MarketRelationship model
    - `volume_stats.py` - VolumeStats aggregation model
  - `api/` - FastAPI routers
    - `alerts.py` - Alerts CRUD
    - `markets.py` - Markets listing
    - `arbitrage.py` - Arbitrage opportunities and relationships
    - `orderbook.py` - Order book analytics
    - `volume.py` - Volume statistics
    - `mm.py` - Market maker analytics
  - `jobs/scheduler.py` - APScheduler background jobs
  - `tests/` - pytest test suite
- `frontend/` - React + TypeScript frontend
  - `src/pages/` - Dashboard pages (Alerts, Arbitrage, OrderBook, Volume, MarketMaker)
  - `src/hooks/` - React Query hooks
  - `src/api/` - API client functions

## Key Configuration

- `ENABLE_SCHEDULER=true` - Set on ONE worker only to run background jobs
- Analysis job runs hourly, trade collection every 5min, orderbook/market sync every 15min

## Testing

```bash
cd backend && source venv/bin/activate && pytest -v
```

## Current Phase

**All phases complete:**

Phase 6 complete - Spec Alignment:
- MarketRelationship model for cross-market tracking
- VolumeStats model for aggregated trading data
- Cross-market arbitrage detection (4 types: mutually_exclusive, conditional, time_sequence, subset)
- Relationship detector for automatic market pairing

Phase 5 complete - Frontend Dashboards:
- ArbitragePage - Cross-market opportunities
- OrderBookPage - Depth analysis, slippage calculator
- VolumePage - Volume leaders and spike alerts
- MarketMakerPage - MM presence and pullback alerts

Phase 4 complete - API endpoints:
- Alerts: CRUD operations with filters
- Markets: List with alert counts, detail view
- Arbitrage: `/api/arbitrage/opportunities`, `/groups`, `/relationships`
- Orderbook: `/api/orderbook/{token}/slippage`, `/patterns`, `/best-hours`
- Volume: `/api/volume/{token}/stats`, `/spikes`, `/leaders`
- Market Maker: `/api/mm/{token}/presence`, `/pullbacks`, `/best-hours`

Phase 3 complete - Analysis engine with:
- VolumeAnalyzer (3x spike threshold, 7-day baseline, acceleration)
- SpreadAnalyzer (5% threshold)
- MarketMakerAnalyzer (50% depth drop)
- ArbitrageDetector (2% min profit, orderbook-first with market price fallback)
- OrderbookAnalyzer (slippage calc, spread patterns, best hours)
- CrossMarketArbitrageDetector (4 relationship types)

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
