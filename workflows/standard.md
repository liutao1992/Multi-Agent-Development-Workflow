# Standard Workflow

Use for normal feature development and medium-risk changes.

```text
Lead → TASK.md + STATUS CREATED
 ↓
Implementation → PLAN-v001
 ↓
Lead Plan Gate
 ├─ REWORK → PLAN-v002
 └─ APPROVED
       ↓
STATUS READY_FOR_IMPLEMENTATION
 ↓
Implementation → code + tests + commit
 ↓
IMPL-001 binds Base SHA / Head SHA
 ↓
STATUS READY_FOR_REVIEW
 ↓
Fresh Review verifies exact Head SHA
 ↓
REVIEW-001
 ├─ FAIL → Lead confirms RW-xxx → REWORK → IMPL-002 → REVIEW-002
 └─ PASS → READY_FOR_FINAL_ACCEPTANCE
              ↓
            Lead → ACCEPTANCE.md
              ↓
            ACCEPTED
```

Required gates: TASK, lifecycle STATUS, Plan approval unless ALL trivial criteria pass, committed/frozen Review Target, independent Review, and Lead ACCEPTANCE.md.
