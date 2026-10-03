# Review Report

Task ID: TASK-YYYYMMDD-NNN-short-name
Task Name: <human-readable name>
Task Contract Revision: 1
Task Contract Hash: <sha256>
Review Round: 1
Reviewed Implementation: IMPL-001

## Plan Reference

Plan Gate: REQUIRED | SKIPPED
Reviewed Plan Artifact: PLAN-v001.md | N/A
Reviewed Plan Version: 1 | N/A

## Review Target Verification

Task Baseline SHA: <sha>
Previous Head SHA: <sha>
Declared Code Head SHA: <sha>
Observed Code Head SHA: <sha>

Unstaged Diff Clean: YES / NO
Staged Diff Clean: YES / NO
Status Porcelain Clean: YES / NO
Control Plane Excluded: YES / NO

Protocol Status: READY_FOR_REVIEW | REVIEW_TARGET_MISMATCH

If any verification item fails, substantive review stops and Review Result remains N/A.

## Independence

Fresh Execution Context: YES / NO / NOT_SUPPORTED
Impl Private Reasoning Used: NO

## Diff Scope

Full Task Diff:
Task Baseline SHA → Code Head SHA

Current Round Diff:
Previous Head SHA → Code Head SHA

## Review Result

PASS / FAIL / N/A

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
Related: REQ-001, AC-001, PLAN-001 | N/A
Location: <path/symbol>
Problem: <...>
Impact: <...>
Evidence: <...>
Required Outcome: <...>
-->

## Additional Review Tests

### TEST-XXX
<Use the next unused task-global TEST ID.>

Command: `<command>`
Result: PASS / FAIL

## Regression Review

<...>

## Final Reason

<...>
