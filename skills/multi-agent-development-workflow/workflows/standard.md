# Standard Workflow

Use for normal feature work and medium-risk changes.

## Normal path

```text
CREATED
 ↓ Lead
PLANNING
 ↓ Impl writes Plan
PLAN_REVIEW
 ├─ REWORK → PLAN_REWORK → next Plan
 └─ APPROVED
       ↓
READY_FOR_IMPLEMENTATION
 ↓ Lead handoff
IMPLEMENTING
 ↓ Impl commits Code Plane + writes IMPL
READY_FOR_REVIEW
 ↓ Lead
REVIEWING
 ├─ FAIL → REWORK → IMPLEMENTING
 └─ PASS → READY_FOR_FINAL_ACCEPTANCE
              ↓
            ACCEPTANCE.md
              ↓
            ACCEPTED
```

## Fast path

If and only if ALL trivial-task criteria pass:

```text
CREATED
 ↓ Lead records Plan Gate SKIPPED
READY_FOR_IMPLEMENTATION
 ↓
IMPLEMENTING
 ↓
stable Code snapshot + IMPL with Plan=N/A
 ↓
independent Review with Plan=N/A
 ↓
Lead Acceptance with Plan=N/A
```

Review and final acceptance are never skipped.
