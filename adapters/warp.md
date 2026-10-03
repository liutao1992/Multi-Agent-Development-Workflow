# Warp Adapter

## Purpose

Warp is the preferred visual terminal control surface for this workflow.

Warp handles:

- terminal layout
- independent terminal sessions
- visual monitoring
- manual handoffs

Warp does not define:

- task semantics
- acceptance policy
- review policy
- agent role boundaries

Those belong to SKILL.md.

## Default layout

Use one Warp tab with three panes:

```text
┌──────────────────────────────┬──────────────────────────────┐
│ Lead Agent                   │ Implementation Agent         │
│                              │                              │
│ Requirements                 │ Investigate                  │
│ Task Management              │ Plan                         │
│ Plan Approval                │ Implement                    │
│ Rework Decision              │ Test                         │
│ Final Acceptance             │ Report                       │
│                              ├──────────────────────────────┤
│                              │ Review Agent                 │
│                              │                              │
│                              │ Review                       │
│                              │ Test                         │
│                              │ PASS / FAIL                  │
└──────────────────────────────┴──────────────────────────────┘
```

Recommended:

- Left: Lead
- Right top: Implementation
- Right bottom: Review

## Shared working tree mode

Recommended while learning the workflow:

- Lead: read-oriented
- Implementation: production-code writer
- Review: read-oriented

All three panes may use the same repository.

Only Implementation normally modifies production files.

Lead and Review may run safe inspection and test commands.

Avoid repository-mutating commands from Lead/Review unless explicitly required.

## Synchronized input

Do not enable synchronized input across the three panes.

The panes intentionally have different roles and prompts.

## Manual handoff

### Lead → Implementation

```text
Task:
<TASK-ID>

Task directory:
.agent-team/tasks/<TASK-ID>/

Action:
Read TASK.md and produce PLAN.md.

Expected output:
PLAN.md with Status: PENDING_APPROVAL.

Do not modify production code before plan approval.
```

### Lead → Implementation after plan approval

```text
Task:
<TASK-ID>

PLAN.md is approved.

Implement the approved plan, run relevant tests, and produce IMPLEMENTATION.md with Status: READY_FOR_REVIEW.
```

### Implementation → Review

```text
Task:
<TASK-ID>

Read TASK.md, approved PLAN.md, and IMPLEMENTATION.md.
Inspect actual repository changes and perform independent review.
Produce REVIEW.md with PASS or FAIL.
```

### Review → Lead

```text
Task:
<TASK-ID>

Read REVIEW.md and validate the findings.
Decide REWORK or proceed to final acceptance.
```

## Worktree upgrade

For stronger isolation, use:

```text
project-main/
project-implementation/
project-review/
```

Map:

- Lead → main worktree
- Implementation → implementation worktree
- Review → clean review worktree

Use commit SHA / branch / patch / cherry-pick for handoff.

## Automation progression

Recommended progression:

1. Warp + 3 panes + shared working tree + manual handoff.
2. Warp + 3 panes + Git worktrees + commit-based handoff.
3. Warp + agent-specific RPC/subagents/SDK.
4. Automated orchestration while preserving independent Review.
