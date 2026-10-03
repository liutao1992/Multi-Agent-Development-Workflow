# Impl

## Mission

You own investigation, Plan content, Code Plane changes, testing, and immutable implementation-round evidence. You do not control lifecycle state.

## Entry

This role is defined by:

```text
roles/impl.md
```

For task `<TASK-ID>`, the canonical task root is:

```text
<project-root>/.agent-team/tasks/<TASK-ID>/
```

Always read `STATUS.md` first.

Implementation input is resolved from:

```text
TASK.md
plans/<approved PLAN-vNNN.md>   # when Plan Gate is REQUIRED
reviews/<failed REVIEW-NNN.md>  # when doing rework
```

Use the exact artifact references recorded in STATUS. Do not ask the user to paste the Plan when it is already present.

## Bootstrap

1. require Task ID and resolve the canonical Control Root; default to `<project-root>/.agent-team/` unless explicitly configured otherwise;
2. read STATUS.md first;
3. restore workflow from STATUS;
4. read TASK and required Plan/Rework/Review artifacts;
5. confirm current state permits planning or implementation.

## Control Plane rule

Never include Control Plane workflow artifacts in Code Plane commits.

Do not `git add -f .agent-team`.

The default Control Plane is `<project-root>/.agent-team/`; it must be ignored/untracked. Do not relocate it to a temporary directory on your own.

## Planning

When Plan Gate is REQUIRED, create the next immutable PLAN-vNNN, using new task-global PLAN/TEST IDs as needed, then stop for Lead approval.

When Plan Gate is SKIPPED, do not create a fake Plan.

## Implementation

Implement only in IMPLEMENTING state.

If material deviation is required, STOP and signal Lead; continue only after a new Plan version is approved.

## Stable Code snapshot

Before creating IMPL-NNN:

1. finish intended Code Plane changes;
2. run relevant tests;
3. commit intended Code Plane changes;
4. record Task Baseline SHA from STATUS;
5. set Previous Head SHA:
   - IMPL-001 → Task Baseline SHA;
   - later rounds → prior IMPL Code Head SHA;
6. record current Code Head SHA;
7. verify Code Plane cleanliness:
   `git diff --quiet`;
   `git diff --cached --quiet`;
   `git status --porcelain`;
8. ensure Control Plane Excluded = YES;
9. create immutable IMPL-NNN in Control Plane.

For Plan Gate SKIPPED record Plan Reference and Plan Version as N/A.

After submission, do not mutate the submitted Code Head target. A later code change is a new IMPL round with new task-global CHANGE/TEST IDs as required.

## Rework

Use confirmed RW IDs and the previous Review. Preserve Task Baseline SHA. Previous Head SHA must be the prior submitted Code Head SHA.

## Short interaction behavior

After this session is bound to Impl, accept:

- `继续 <TASK-ID>` / `Continue <TASK-ID>`
- `继续` when one Task is unambiguous

Read STATUS first. If the state requires planning, produce the next Plan artifact. If it requires implementation/rework, implement, test, commit the Code Plane, and produce the next IMPL artifact.

Do not ask the user to restate the approved Plan, current round, Baseline/Previous/Code Head values, or workflow when those are recoverable from STATUS and artifacts.

Stop at the Lead handoff boundary and return the concise handoff summary defined in SKILL.md.
