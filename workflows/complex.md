# Complex Workflow

Use for:

- architecture changes
- database migrations
- major refactors
- security-sensitive changes
- concurrency changes
- cross-module changes
- high regression risk

## Flow

```text
Task
 ↓
Technical investigation
 ↓
Plan
 ↓
Plan review
 ↓
Implementation
 ↓
Implementation self-check
 ↓
Independent review
 ↓
Tests / regression review
 ↓
Final acceptance
```

## Additional expectations

PLAN.md should explicitly cover:

- architecture impact
- migration / rollback strategy when relevant
- compatibility
- failure modes
- data integrity
- observability
- test strategy
- rollout constraints

Lead should be stricter about plan approval.

Review should verify both local correctness and system-level impact.
