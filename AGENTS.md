# Agent Coordination

Read before starting work.

## Shared Rules

- Read `.claude/REGISTRY.md` and `.claude/ISSUES.md` first
- Use structured IDs (Q/W/D for registry, I for issues)
- Keep entries short; add details only when helpful
- Codex adds review entries as separate Done lines
- Only Claude moves items across registry sections

## Claude (Builder)

- Implements work and moves Q -> W -> D
- Updates entry fields if scope changes
- Adds follow-ups as new Q-### items
- Moves fixed issues to Resolved in ISSUES.md

## Codex (Supervisor)

- Reviews newly Done items
- Logs review entries in Done section
- Raises issues in `ISSUES.md`
- Never moves registry items

## Entry Formats

### Registry (REGISTRY.md)

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

Review (Codex appends):
```
- D-### | Review: D-### | Reviewer: Codex | YYYY-MM-DD
  - Findings: [summary]
  - Issues: [I-### links if any]
```

### Issues (ISSUES.md)

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

Tags: `[bug]` `[idea]` `[question]` `[test]` `[quality]`
