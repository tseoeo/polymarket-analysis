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
- `SCHEDULER_INTERVAL_MINUTES` - Data collection frequency (default: 15)
- `LOG_LEVEL` - Logging level (default: INFO)

## API Endpoints

- `GET /api/health` - Health check
- `GET /api/info` - API information

More endpoints coming in future phases.

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
- [ ] Phase 2: Data Collection
- [ ] Phase 3: Analysis Engine
- [ ] Phase 4: API Layer
- [ ] Phase 5: React Dashboard
- [ ] Phase 6: Polish
