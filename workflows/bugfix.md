# Bugfix Workflow

Use for defect investigation and repair.

## TASK.md additions

Record when available:

- Expected Behavior
- Actual Behavior
- Reproduction Steps
- Environment
- Frequency / conditions
- Known regression range

## Flow

```text
Bug task
 ↓
Reproduce
 ↓
Root-cause investigation
 ↓
Fix plan
 ↓
Lead plan approval
 ↓
Implementation
 ↓
Regression test
 ↓
Review
 ↓
Final acceptance
```

## Requirements

Implementation should identify the root cause rather than only suppressing the symptom.

Testing should include:

1. a case that reproduces the original defect;
2. proof that the fix resolves it;
3. regression coverage for adjacent behavior when appropriate.
