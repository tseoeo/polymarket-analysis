# Polymarket Analysis Tool

A web-based analysis tool for discovering Polymarket trading opportunities through:

- **Cross-Market Arbitrage Detection** - Find mispriced related markets
- **Order Book Analysis** - Analyze liquidity, spreads, and depth
- **Volume Anomaly Detection** - Spot unusual trading activity
- **Market Maker Pattern Analysis** - Understand liquidity provider behavior

## Deployment

This application is designed to run on [Railway](https://railway.app).

### Setup

1. Create a new Railway project
2. Add the PostgreSQL plugin
3. Connect this GitHub repository
4. Railway will auto-deploy

### Environment Variables

Railway will automatically set `DATABASE_URL` when you add PostgreSQL.

Optional configuration:
- `ENABLE_SCHEDULER` - Enable background jobs (default: false, see below)
- `SCHEDULER_INTERVAL_MINUTES` - Data collection frequency (default: 15)
- `LOG_LEVEL` - Logging level (default: INFO)

### Scheduler Configuration

Set `ENABLE_SCHEDULER=true` on exactly **ONE** service/worker to avoid duplicate jobs.

If scaling to multiple replicas, create a separate "worker" service with the scheduler enabled and keep web replicas with it disabled.

## API Endpoints

### Core Endpoints
- `GET /api/health` - Health check
- `GET /api/info` - API information

### Alerts
- `GET /api/alerts` - List alerts with filters
- `GET /api/alerts/{id}` - Alert details
- `PATCH /api/alerts/{id}/dismiss` - Dismiss alert

### Markets
- `GET /api/markets` - List markets with alert counts
- `GET /api/markets/{id}` - Market details
- `GET /api/markets/{id}/alerts` - Market alerts

### Arbitrage
- `GET /api/arbitrage/opportunities` - List arbitrage opportunities
- `GET /api/arbitrage/groups` - List market relationship groups
- `GET /api/arbitrage/groups/{group_id}` - Group details
- `POST /api/arbitrage/relationships` - Create relationship
- `DELETE /api/arbitrage/relationships/{id}` - Remove relationship
- `POST /api/arbitrage/detect` - Trigger detection job

### Order Book
- `GET /api/orderbook/{token_id}` - Current orderbook with metrics
- `GET /api/orderbook/{token_id}/slippage` - Slippage calculator
- `GET /api/orderbook/{token_id}/patterns` - Spread patterns by hour
- `GET /api/orderbook/{token_id}/best-hours` - Best trading hours

### Volume
- `GET /api/volume/{token_id}/stats` - Volume metrics
- `GET /api/volume/spikes` - Markets with volume anomalies
- `GET /api/volume/leaders` - Top volume markets

### Market Maker
- `GET /api/mm/{token_id}/presence` - MM activity score
- `GET /api/mm/{token_id}/patterns` - Activity patterns by hour
- `GET /api/mm/pullbacks` - Active MM pullback alerts
- `GET /api/mm/best-hours` - Best trading hours across markets

## Architecture

```
┌─────────────────────────────────────────────────┐
│            Railway Service                       │
│  ┌───────────────────────────────────────────┐  │
│  │         FastAPI Application               │  │
│  │  • /api/* routes (REST API)               │  │
│  │  • Static files (React build)             │  │
│  │  • APScheduler (background jobs)          │  │
│  └───────────────────────────────────────────┘  │
│                      │                           │
│                      ▼                           │
│  ┌───────────────────────────────────────────┐  │
│  │      PostgreSQL (Railway Plugin)          │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## Development Status

- [x] Phase 1: Foundation (FastAPI + PostgreSQL)
- [x] Phase 2: Data Collection (Markets, Trades, OrderBook Snapshots)
- [x] Phase 3: Analysis Engine (Volume, Spread, MM, Arbitrage analyzers)
- [x] Phase 4: API Layer (Alerts, Markets, Arbitrage, Orderbook, Volume, MM endpoints)
- [x] Phase 5: React Dashboard (Dashboard, Alerts, Arbitrage, Orderbook, Volume, MarketMaker pages)
- [x] Phase 6: Spec-Alignment (Cross-market relationships, advanced analytics)

## Features

### Cross-Market Arbitrage Detection
Detects four types of market relationship arbitrage:
- **Type A (Mutually Exclusive)**: Markets that sum > 100% (e.g., "Trump wins" + "Biden wins")
- **Type B (Conditional)**: Child probability exceeds parent (e.g., "Trump wins PA" > "Trump wins")
- **Type C (Time Sequence)**: Earlier event priced higher than later (e.g., "Passes House" vs "Becomes law")
- **Type D (Subset)**: Specific market exceeds general (e.g., "Trump wins by >10%" > "Trump wins")

### Order Book Analysis
- Real-time spread and depth monitoring
- Slippage calculator for trade sizing
- Hourly pattern analysis to find best trading times
- Depth at 1%, 5%, 10% price levels

### Volume Analytics
- 7-day volume baseline calculation
- Volume acceleration detection (sudden spikes)
- Volume-price correlation analysis
- OHLC price tracking

### Market Maker Detection
- MM presence scoring based on spread consistency
- Liquidity pullback alerts when depth drops
- Activity pattern analysis by hour
