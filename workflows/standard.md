# Standard Workflow

Use for normal feature development and medium-risk changes.

## Flow

```text
Lead creates TASK
 ↓
Implementation investigates
 ↓
Implementation creates PLAN
 ↓
Lead approves PLAN
 ↓
Implementation implements + tests
 ↓
Implementation creates IMPLEMENTATION
 ↓
Review independently verifies
 ↓
Review creates REVIEW
 ├─ FAIL → Lead validates → REWORK
 └─ PASS → Lead final acceptance
```

## Required gates

1. TASK.md exists.
2. PLAN.md approved before substantial production changes.
3. IMPLEMENTATION.md says READY_FOR_REVIEW.
4. REVIEW.md says PASS.
5. Lead performs final acceptance.

## Fast path

For a trivial low-risk task, Lead may record:

```text
Plan Gate: SKIPPED
Reason: <reason>
```

The Review and final-acceptance gates remain.
