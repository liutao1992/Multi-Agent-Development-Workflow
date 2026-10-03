# Review Report

Task ID: TASK-YYYYMMDD-NNN-short-name
Task Name: <human-readable name>
Review Round: 1
Reviewed Implementation: IMPL-001
Reviewed Plan Version: 1

## Review Target Verification

Declared Base SHA: <sha>
Declared Head SHA: <sha>
Observed Head SHA: <sha>
Target Match: YES / NO

If NO, substantive review stops with REVIEW_TARGET_MISMATCH.

## Independence

Fresh Execution Context: YES / NO / NOT_SUPPORTED
Implementation Private Reasoning Used: NO

Artifacts Used:
- TASK.md
- PLAN-v001.md
- IMPL-001.md
- Base→Head diff
- test evidence

## Result

PASS / FAIL / REVIEW_TARGET_MISMATCH

## Requirement Verification

| Requirement | Result | Evidence |
|---|---|---|
| REQ-001 | PASS / FAIL | <evidence> |

## Acceptance Criteria

| Criterion | Result | Evidence |
|---|---|---|
| AC-001 | PASS / FAIL | <evidence> |

## Blocking Issues

None

<!--
### REV-001
Severity: BLOCKING
Related: REQ-001, AC-001, PLAN-001
Location: <path/symbol>
Problem: <...>
Impact: <...>
Evidence: <...>
Required Outcome: <...>
-->

## Non-blocking Suggestions

None

## Tests Performed

### TEST-REVIEW-001
Command: `<command>`
Result: PASS / FAIL

## Regression Review

<...>

## Final Reason

<...>
