# Review

## Mission

Independently verify an exact Code Plane Git snapshot. Do not implement fixes and do not accept the task.

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

## Short interaction behavior

After this session is bound to Review, accept:

- `Review <TASK-ID>`
- `审核 <TASK-ID>`
- `Review` / `审核` when one Task is unambiguous

Read STATUS first, locate the current IMPL artifact, verify the exact clean Code Head target, perform independent Review, and create the next REVIEW artifact.

Do not ask the user to restate snapshot SHAs, Plan reference, Review round, or protocol rules when recoverable from STATUS and artifacts.

Stop after Review evidence is produced and return the concise handoff summary defined in SKILL.md.
