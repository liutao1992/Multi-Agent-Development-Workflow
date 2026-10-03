# Bugfix Workflow

TASK should record Expected Behavior, Actual Behavior, Reproduction Steps, Environment, frequency/conditions, and regression range when available.

Task Baseline SHA is frozen before the fix.

```text
Bug Task
 ↓
Reproduce / root cause
 ↓
Plan Gate unless ALL trivial criteria pass
 ↓
Fix + regression tests
 ↓
commit Code Plane
 ↓
IMPL-NNN with Baseline / Previous / Code Head
 ↓
independent Review at clean exact Code Head
 ↓
Lead Acceptance
```

Review should inspect both the full task diff and, for rework, the delta from the previous submitted Head.

An uncommitted, dirty, or Control-Plane-contaminated review target is invalid.
