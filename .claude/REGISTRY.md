# Registry

> Work tracking for Claude (builder) and Codex (supervisor).
> Read before starting. Keep entries short.

## Queue

<!-- Planned work. Only Claude adds/moves items. -->

## In Progress

<!-- Active work. Claude moves here when starting. -->

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

- D-005 | CLOB API tradeable market filtering | Owner: Claude | 2025-01-25
  - Outcome: Fixed 404/429 errors by only querying tradeable markets
  - Files: backend/services/polymarket_client.py, backend/config.py
  - Tests: not run (deployed, awaiting verification)

- D-006 | Trade collection enable_order_book filter | Owner: Claude | 2025-01-25
  - Outcome: Fixed trade collection to filter by enable_order_book=True (was querying all 20k markets)
  - Files: backend/services/polymarket_client.py:469
  - Tests: not run (deployed, awaiting verification)

- D-005 | Review: D-005 | Reviewer: Codex | 2026-01-25
  - Findings: Verify CLOB token ID source (token_id vs condition_id); skip inactive/untradeable tokens; treat 404s as non-fatal and rely on backoff for 429s
  - Issues: I-001

- D-007 | HMAC signature fix (input) | Owner: Claude | 2026-01-25
  - Outcome: Fixed secret decoding to use urlsafe_b64decode
  - Files: backend/services/polymarket_client.py:103
  - Tests: not run (still getting 401 - output encoding also wrong)

- D-009 | HMAC signature fix (output) | Owner: Claude | 2026-01-25
  - Outcome: Fixed signature output to use urlsafe_b64encode (not b64encode)
  - Files: backend/services/polymarket_client.py:105
  - Tests: not run (still 401 - query params shouldn't be signed)

- D-010 | HMAC signature fix (path) | Owner: Claude | 2026-01-25
  - Outcome: Sign only base path (/trades), not query params (?token_id=...)
  - Files: backend/services/polymarket_client.py:145-161
  - Tests: not run (auth working, but 0 trades - wrong endpoint)

- D-011 | Fix trades endpoint path | Owner: Claude | 2026-01-25
  - Outcome: Changed /trades to /data/trades, token_id to asset_id, trades to data
  - Files: backend/services/polymarket_client.py:405-415
  - Tests: not run (CLOB trades endpoint only returns user's own trades - 0 found)

- D-012 | Switch to Data API for trades | Owner: Claude | 2026-01-25
  - Outcome: Use data-api.polymarket.com instead of CLOB API for public trade data
  - Files: backend/services/polymarket_client.py
  - Tests: not run (deployed, awaiting verification)

- D-008 | Initial collection triggers | Owner: Claude | 2026-01-25
  - Outcome: Added startup triggers for orderbook (45s) and trade (60s) collection
  - Files: backend/jobs/scheduler.py
  - Tests: not run (deployed, awaiting verification)

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
