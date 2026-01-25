# Issues

> Bugs, ideas, questions. Either agent can write.
> Check before starting work. Reference by ID.

## Open

<!-- New issues go here -->
- I-001 | [bug] | CLOB API returns 404 for many token IDs | Found by: Claude | 2025-01-25
  - Context: Orderbook/trade collection fails with 404 Not Found for tokens from Gamma API
  - Evidence: Railway logs show 404 for /book?token_id=... and /trades?token_id=...
  - Suggested fix: Verify if Gamma API token IDs are valid for CLOB; may need different API endpoint or filtering

## In Progress

<!-- Issues being worked on -->

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
