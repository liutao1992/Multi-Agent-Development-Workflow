---
name: multi-agent-development-workflow
description: Runtime-independent three-role software-development workflow with task namespaces, plan approval, independent review, rework loops, final acceptance, and Warp-first terminal coordination.
---

# Multi-Agent Development Workflow

## Purpose

Use this skill for non-trivial software-development work that benefits from separating:

1. **Lead Agent** — defines what should be built and owns final acceptance.
2. **Implementation Agent** — investigates, plans, implements, tests, and reports.
3. **Review Agent** — independently verifies whether the implementation is correct.

The workflow is runtime-independent. It may be used with Codex, Pi, Claude Code, Cursor, OpenCode, or other coding agents.

Warp is the preferred interactive terminal environment, but terminal software is an adapter rather than part of the core protocol.

## Core rule

Never collapse these questions into one role:

- **What should be built?** → Lead Agent
- **How should it be built?** → Implementation Agent
- **Was it built correctly?** → Review Agent

Only the Lead Agent may declare a task **ACCEPTED**.

## Coordination structure

Each task gets its own namespace:

```text
.agent-team/
├── INDEX.md
└── tasks/
    ├── TASK-YYYYMMDD-NNN-short-name/
    │   ├── TASK.md
    │   ├── PLAN.md
    │   ├── IMPLEMENTATION.md
    │   ├── REVIEW.md
    │   └── STATUS.md
    └── ...
```

Do not use one global TASK.md or PLAN.md for multiple independent tasks.

## Task ID

Use:

```text
TASK-YYYYMMDD-NNN-short-name
```

Example:

```text
TASK-20261003-001-word-review-redesign
```

The directory name is the task namespace. Internal documents must also record the Task ID and Task Name.

## Source of truth

Use this priority:

1. TASK.md
2. approved PLAN.md
3. repository state
4. IMPLEMENTATION.md
5. REVIEW.md
6. conversation history

When conversation history conflicts with task files, the Lead Agent must resolve the discrepancy and update the task files.

## Standard lifecycle

```text
User
 ↓
Lead
 ↓
TASK.md
 ↓
Implementation investigates
 ↓
PLAN.md
 ↓
Lead plan review
 ├─ PLAN_REWORK → Implementation
 └─ APPROVED
       ↓
Implementation
 ↓
Tests
 ↓
IMPLEMENTATION.md
 ↓
Review
 ↓
REVIEW.md
 ├─ FAIL → Lead validates → REWORK → Implementation
 └─ PASS
       ↓
Lead final acceptance
 ├─ REWORK
 └─ ACCEPTED
```

## Plan gate

For substantial work, implementation must not begin until PLAN.md is approved.

The Lead Agent may explicitly skip the plan gate only for a trivial, low-risk task and must record the reason.

## Stable identifiers

Use stable identifiers for traceability:

- Requirements: `REQ-001`
- Acceptance criteria: `AC-001`
- Plan steps: `PLAN-001`
- Implementation changes: `CHANGE-001`
- Tests: `TEST-001`
- Review findings: `REV-001`
- Rework items: `RW-001`

Preferred traceability:

```text
REQ-001
  ↓
AC-001
  ↓
PLAN-001
  ↓
CHANGE-001
  ↓
TEST-001
  ↓
Review evidence
```

## Handoff contract

Every handoff must identify:

- Task ID
- Task directory
- requested action
- expected output

Example:

```text
Task:
TASK-20261003-001-word-review-redesign

Task directory:
.agent-team/tasks/TASK-20261003-001-word-review-redesign/

Action:
Read TASK.md, investigate the current implementation, and produce PLAN.md.

Expected output:
PLAN.md with Status: PENDING_APPROVAL.

Do not modify production code before plan approval.
```

## Multiple active tasks

Never infer the active task when multiple tasks are active.

Always name the Task ID and task directory explicitly before performing task work.

## Role boundaries

### Lead Agent

Owns:

```text
Understand
→ Define
→ Create Task
→ Approve Plan
→ Evaluate Review
→ Manage Rework
→ Final Acceptance
```

Normally does not implement the main production change.

### Implementation Agent

Owns:

```text
Investigate
→ Plan
→ Implement
→ Test
→ Self-check
→ Report
```

May declare `READY_FOR_REVIEW`, but never `ACCEPTED`.

### Review Agent

Owns:

```text
Inspect
→ Challenge
→ Verify
→ Test
→ PASS / FAIL
```

Normally does not fix the implementation itself.

## Review policy

A Review Agent must inspect actual repository state, not only the implementation report.

Review relevant:

- TASK.md
- approved PLAN.md
- IMPLEMENTATION.md
- git diff / changed files
- related source files
- tests
- regression risk
- scope compliance

A review result is only:

- PASS
- FAIL

The reviewer must not issue final acceptance.

## Blocking issue policy

Blocking findings affect one or more of:

- correctness
- explicit requirements
- acceptance criteria
- data integrity
- stability
- security
- required compatibility
- significant architectural constraints

Normally non-blocking:

- personal naming preferences
- minor formatting preferences
- optional cleanup
- speculative future improvements

## Rework

When Review returns FAIL, the Lead Agent validates the findings.

Confirmed blocking findings become `RW-xxx` entries in TASK.md.

Do not blindly convert every reviewer suggestion into required work.

A re-review must check:

- previous blocking issues
- new diff
- original requirements
- original acceptance criteria
- new regression risk

Fixing the old issue alone does not automatically produce PASS.

## Final acceptance

After Review PASS, the Lead Agent must independently confirm:

1. Objective achieved.
2. Requirements satisfied.
3. Acceptance criteria satisfied.
4. Approved plan was appropriately implemented.
5. Review PASS is justified.
6. No blocking defect remains.
7. No unacceptable regression exists.
8. No accidental unrelated change remains.
9. Testing evidence is sufficient.

Only then set status to `ACCEPTED`.

## Recommended states

```text
CREATED
PLANNING
PLAN_REVIEW
PLAN_REWORK
READY_FOR_IMPLEMENTATION
IMPLEMENTING
READY_FOR_REVIEW
REVIEWING
REWORK
READY_FOR_FINAL_ACCEPTANCE
ACCEPTED
BLOCKED
CANCELLED
```

## Workflow selection

Use:

- `workflows/standard.md` for normal feature work.
- `workflows/complex.md` for architectural, migration, security-sensitive, or high-regression-risk changes.
- `workflows/bugfix.md` for defect investigation and repair.

## Runtime and terminal adapters

Core workflow rules must not be rewritten for a particular product.

Use:

- `adapters/warp.md` for Warp terminal layout.
- `runtimes/pi.md` for Pi-specific notes.
- `runtimes/codex.md` for Codex-specific notes.
- `runtimes/generic.md` for other agents.

Runtime adapters may describe startup, tools, isolation, RPC, subagents, or sandbox behavior, but must preserve the same Lead → Implementation → Review → Lead protocol.
