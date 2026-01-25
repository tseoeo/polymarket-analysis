# Registry

> Work tracking for Claude (builder) and Codex (supervisor).
> Read before starting. Keep entries short.

## Queue

<!-- Planned work. Only Claude adds/moves items. -->

## In Progress

<!-- Active work. Claude moves here when starting. -->
- W-001 | CLOB API data collection | Owner: Claude | Started: 2025-01-25
  - Scope: Fix 404/429 errors preventing orderbook/trade collection
  - Files: backend/services/polymarket_client.py, backend/config.py
  - Risks: Polymarket may have changed API; many tokens return 404

## Done

<!-- Completed work + review entries. -->
- D-000 | Project baseline | Owner: - | 2025-01-25
  - Outcome: FastAPI backend with Polymarket data collection, 4 analyzers (volume, spread, MM, arbitrage), alert/market API endpoints
  - Files: backend/ (models, services, api, jobs)
  - Tests: `pytest -v` - 89 tests passing

- D-001 | Phase 3: Analysis engine | Owner: Claude | 2025-01-25
  - Outcome: Implemented VolumeAnalyzer, SpreadAnalyzer, MarketMakerAnalyzer, ArbitrageDetector
  - Files: backend/services/*_analyzer.py, backend/services/arbitrage_detector.py
  - Tests: pytest tests/test_phase3*.py - all passing

- D-002 | Phase 4: Alert & Market API | Owner: Claude | 2025-01-25
  - Outcome: REST endpoints for alerts (list, get, dismiss) and markets (list, get, alerts)
  - Files: backend/api/alerts.py, backend/api/markets.py, backend/main.py
  - Tests: pytest tests/test_phase4_api.py - 17 tests passing

- D-003 | Datetime timezone fix | Owner: Claude | 2025-01-25
  - Outcome: Fixed "can't subtract offset-naive and offset-aware datetimes" error
  - Files: backend/services/polymarket_client.py (lines 188-232)
  - Tests: not run (deployed to Railway, verified in logs)

- D-004 | JSON string parsing fix | Owner: Claude | 2025-01-25
  - Outcome: Fixed parsing of clobTokenIds/outcomes as JSON strings from Gamma API
  - Files: backend/services/polymarket_client.py
  - Tests: not run (deployed, markets now sync with 10k+ records)

## Templates

Queue:
```
- Q-### | [topic] | Owner: Claude | Status: open
  - Goal: [one line]
  - Success: [definition of done]
```

In Progress:
```
- W-### | [topic] | Owner: Claude | Started: YYYY-MM-DD
  - Scope: [what is being done]
  - Files: [if relevant]
  - Risks: [if known]
```

Done:
```
- D-### | [topic] | Owner: Claude | YYYY-MM-DD
  - Outcome: [what was achieved]
  - Files: [what changed]
  - Tests: [command + result] or "not run"
```

Review:
```
- D-### | Review: D-### | Reviewer: Codex | YYYY-MM-DD
  - Findings: [summary]
  - Issues: [I-### links if any]
```
