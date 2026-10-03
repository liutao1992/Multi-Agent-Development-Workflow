# Bugfix Workflow

TASK should record Expected Behavior, Actual Behavior, Reproduction Steps, Environment, frequency/conditions, and regression range when available.

```text
Bug Task
 ↓
Reproduce
 ↓
Root cause
 ↓
PLAN-vNNN
 ↓
Plan Gate unless ALL trivial criteria pass
 ↓
Fix + regression tests
 ↓
Commit stable Review Target
 ↓
IMPL-NNN
 ↓
Independent Review at exact Head SHA
 ↓
REVIEW-NNN
 ↓
Lead ACCEPTANCE.md
```

Testing should reproduce the original defect, prove the fix, and cover adjacent regressions when appropriate.

Review of an uncommitted or moving target is invalid.
