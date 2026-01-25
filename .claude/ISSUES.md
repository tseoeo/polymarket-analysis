# Issues

> Bugs, ideas, questions. Either agent can write.
> Check before starting work. Reference by ID.

## Open

<!-- New issues go here -->
- I-004 | [question] | Verify data pipeline working end-to-end | Found by: Claude | 2026-01-25
  - Context: All fixes deployed, need to verify in Railway logs
  - Evidence: Awaiting logs showing successful trade/orderbook collection
  - Success criteria: 1) "Trade collection complete: X new" with X > 0, 2) No 401 errors

## In Progress

<!-- Issues being worked on -->
- I-001 | [bug] | CLOB API returns 404 for many token IDs | Assigned: Claude | 2025-01-25
  - Working on: Fixed via enableOrderBook/acceptingOrders filtering (D-005). Awaiting verification.

- I-002 | [bug] | 401 Unauthorized on /trades endpoint | Assigned: Claude | 2026-01-25
  - Working on: Fixed HMAC signature (D-007) - was using b64decode instead of urlsafe_b64decode. Awaiting verification.

- I-003 | [bug] | Trade collection not running after deploy | Assigned: Claude | 2026-01-25
  - Working on: Fixed scheduler (D-008) - added startup triggers at 45s/60s. Awaiting verification.

## Resolved

<!-- Fixed or closed -->

## Templates

Open:
```
- I-### | [bug/idea/question/test/quality] | [topic] | Found by: [agent] | YYYY-MM-DD
  - Context: [brief explanation]
  - Evidence: [file/line or repro]
  - Suggested fix: [if known]
```

In Progress:
```
- I-### | [tag] | [topic] | Assigned: Claude | YYYY-MM-DD
  - Working on: [approach]
```

Resolved:
```
- I-### | [tag] | [topic] | Fixed by: Claude | YYYY-MM-DD
  - Resolution: [what was done]
```
