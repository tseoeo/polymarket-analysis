# Registry

> Work tracking for Claude (builder) and Codex (supervisor).
> Read before starting. Keep entries short.

## Queue

<!-- Planned work. Only Claude adds/moves items. -->

## In Progress

<!-- Active work. Claude moves here when starting. -->
- W-017 | Spec: Precision & Efficiency (12 items) | Owner: Claude | Started: 2026-02-06
  - Scope: All 12 items from SPEC-precision-efficiency.md
  - Files: backend/config.py, backend/jobs/scheduler.py, backend/services/*.py, backend/models/alert.py
  - Risks: Concurrent analyzer change affects all analyzers

- W-018 | Spec: Understandability (7 sections) | Owner: Claude | Started: 2026-02-06
  - Scope: All 7 sections from SPEC-understandability.md
  - Files: frontend/src/lib/explanations.ts, frontend/src/pages/*.tsx
  - Risks: Label-only changes, low risk

- W-019 | Spec: Future Improvements (9 items) | Owner: Claude | Started: 2026-02-06
  - Scope: All 9 items from SPEC-future-improvements.md
  - Files: backend/services/*.py, backend/api/health.py, frontend/src/pages/*.tsx
  - Risks: Some items touch analysis logic



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
  - Tests: not run (429 rate limits from per-token requests)

- D-013 | Optimize trade collection | Owner: Claude | 2026-01-25
  - Outcome: Fetch all trades in 1 request, filter locally (was 500+ requests)
  - Files: backend/services/polymarket_client.py:548-620
  - Tests: not run (deployed, awaiting verification)

- D-008 | Initial collection triggers | Owner: Claude | 2026-01-25
  - Outcome: Added startup triggers for orderbook (45s) and trade (60s) collection
  - Files: backend/jobs/scheduler.py
  - Tests: not run (deployed, awaiting verification)

- D-XXX | Review: UX revamp | Reviewer: Codex | 2026-01-25
  - Findings: SafetyScorer only checks related_market_ids (misses market_id alerts); watchlist uses score after exceptions; teach-me mapping misses spread_alert/mm_pullback; truthy checks mishandle 0 values; daily briefing may be slow without batching
  - Issues: see .claude/plans/ux-revamp-review.md

- D-016 | Opportunity explanations + actionability | Owner: Claude | 2026-02-01
  - Outcome: New opportunity_explainer service with per-type profit estimates (conservative/optimistic per €1), best_time_to_act (act_now/watch/wait), 4 signal templates (arbitrage/spread/volume/mm), integrated into briefing + detail APIs and frontend cards/detail page
  - Files: backend/services/opportunity_explainer.py (new), backend/api/briefing.py, backend/services/safety_scorer.py, frontend/src/api/briefing.ts, frontend/src/pages/DailyBriefingPage.tsx, frontend/src/pages/OpportunityDetailPage.tsx, backend/tests/test_opportunity_explainer.py (new)
  - Tests: pytest tests/test_opportunity_explainer.py tests/test_safety_scorer.py - 19 passed

- D-015 | Fix briefing perf + two-tier fallback | Owner: Claude | 2026-02-01
  - Outcome: SQL pre-filter by alert count + orderbook freshness (N+1 fix), two-tier safe/learning scoring, updated API schema with fallback fields, frontend learning picks UI with amber warnings, 3 new tests
  - Files: backend/services/safety_scorer.py, backend/api/briefing.py, frontend/src/pages/DailyBriefingPage.tsx, frontend/src/api/briefing.ts, backend/tests/test_safety_scorer.py
  - Tests: pytest tests/test_safety_scorer.py tests/test_integration.py tests/test_advanced_analytics.py - 27 passed

- D-014 | Fix slow daily briefing endpoint | Owner: Claude | 2026-02-01
  - Outcome: Pre-filter markets via SQL subquery join on recent orderbook snapshots, fixing N+1 query problem
  - Files: backend/services/safety_scorer.py (get_safe_opportunities)
  - Tests: pytest tests/test_safety_scorer.py tests/test_advanced_analytics.py tests/test_integration.py - 24 passed

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
