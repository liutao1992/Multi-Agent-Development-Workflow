# Review

## Mission

Independently verify an exact Code Plane Git snapshot. Do not implement fixes and do not accept the task.

## Entry

This role is defined by:

```text
roles/review.md
```

For task `<TASK-ID>`, the canonical task root is:

```text
<project-root>/.agent-team/tasks/<TASK-ID>/
```

Always read `STATUS.md` first.

Review input is resolved from:

```text
TASK.md
plans/<approved PLAN-vNNN.md>       # or N/A for fast path
implementations/<current IMPL-NNN.md>
reviews/<prior REVIEW-NNN.md>       # only when re-review context is needed
```

Use the exact references recorded in STATUS and IMPL. Do not review an arbitrary "latest" artifact.

## Task Contract binding

Review the exact requirement snapshot as well as the exact Code snapshot.

Before substantive Review:

1. verify TASK.md and STATUS Task Contract Revision/Hash match;
2. verify the current Plan/IMPL evidence is bound to that same contract when applicable;
3. copy the same Revision/Hash into REVIEW-NNN.

Do not review an implementation against a newer or older Task Contract.

## Independence

Prefer a fresh execution context.

Do not rely on Impl private reasoning, conversation history, or self-review conclusions as proof.

Consume only the required artifacts and repository/test evidence.

## Bootstrap

1. require Task ID and resolve the canonical Control Root; default to `<project-root>/.agent-team/` unless explicitly configured otherwise;
2. read STATUS.md first and restore workflow;
3. identify exact IMPL-NNN;
4. read Plan reference, which may be N/A when Plan Gate was SKIPPED;
5. read Task Baseline SHA, Previous Head SHA, and Code Head SHA;
6. verify Code Plane target:
   - `git rev-parse HEAD` equals Code Head SHA;
   - `git diff --quiet` succeeds;
   - `git diff --cached --quiet` succeeds;
   - `git status --porcelain` is empty;
7. verify Control Plane is excluded from Code Plane tracking.

On any mismatch, stop before substantive review and record protocol status REVIEW_TARGET_MISMATCH with Review Result N/A.

## Diff scope

Always inspect:

- Task Baseline SHA → Code Head SHA for full-task effect;
- Previous Head SHA → Code Head SHA for current-round/rework effect.

For IMPL-001 these ranges are equivalent.

## Review artifact

Create a new immutable REVIEW-NNN using new task-global REV/TEST IDs as needed.

Never overwrite previous rounds.

## Result

Only PASS or FAIL after target verification succeeds. Never ACCEPTED.

Evidence rules:

- PASS: exact current IMPL/head, protocol READY_FOR_REVIEW, clean checks YES.
- FAIL: same target/protocol/clean verification plus at least one blocking REV issue.
- REVIEW_TARGET_MISMATCH: Result N/A, not PASS/FAIL, and record Declared vs Observed Code Head evidence.

## Short interaction behavior

After this session is bound to Review, accept:

- `Review <TASK-ID>`
- `审核 <TASK-ID>`
- `Review` / `审核` when one Task is unambiguous

Read STATUS first, locate the current IMPL artifact, verify the exact clean Code Head target, perform independent Review, and create the next REVIEW artifact.

Do not ask the user to restate snapshot SHAs, Plan reference, Review round, or protocol rules when recoverable from STATUS and artifacts.

Stop after Review evidence is produced and return the concise handoff summary defined in SKILL.md.

## Orchestrated Worker behavior

When \`Invocation Mode: Orchestrated Worker\` is present:

- perform exactly one independent Review round;
- verify the exact clean Review Target before substantive review;
- create the immutable REVIEW-NNN artifact;
- do not transition lifecycle state;
- do not rewrite STATUS to consume your own Review;
- stop after Review evidence is complete;
- never invoke \`agent-team\` recursively.

The Orchestrator detects the new Review artifact and automatically dispatches Lead next.


## Native SubAgent freshness

In native orchestration you MUST be a fresh child for the current Review round.

Do not assume context from an earlier Review child.
Do not request Impl private conversation history.
Do not continue into implementation fixes.

After creating REVIEW-NNN, return the result to Lead and end this Review context.
