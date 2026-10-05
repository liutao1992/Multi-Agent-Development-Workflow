# Review

## Mission

Independently verify an exact Code Plane Git snapshot. Do not implement fixes and do not accept the task.

## Task inputs

Read STATUS first and load only current-action artifacts. Shared workspace,
loading and tmux handoff rules are in `interactive.md` (Process workers use
`automation/worker-brief.md`).

Read TASK, the exact current IMPL and approved Plan (or fast-path marker). Read
a prior REVIEW only when needed for re-review.

## Task Contract binding

Review the exact requirement snapshot as well as the exact Code snapshot.

Before substantive Review:

1. verify TASK.md and STATUS Task Contract Revision/Hash match;
2. verify the current Plan/IMPL evidence is bound to that same contract when applicable;
3. copy the same Revision/Hash into REVIEW-NNN.

Do not review an implementation against a newer or older Task Contract.

## Independence

Keep the Review context across rounds. Reload current-round authoritative
inputs and independently verify each new head; never reuse an old PASS as proof.

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

For the first submitted IMPL these ranges are equivalent, even if its round
number is greater than 001 after an abnormal handoff.

## Review artifact

Create a new immutable REVIEW-NNN using new task-global REV/TEST IDs as needed.

Use `templates/reviews/REVIEW-001.md` for the machine-readable target block:
`Declared Code Head SHA`, `Observed Code Head SHA`, all four cleanliness fields,
and `Protocol Status` must appear as exact field labels on separate lines.
Place the result under `## Review Result`. Narrative checks may supplement these
fields but cannot replace them.

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

In tmux-native mode, signal the completion channel supplied by Lead after REVIEW-NNN is complete; Lead then consumes it.


## Tmux Review behavior

The Review pane and Agent context remain stable across rounds. Lead does not
restart Review before routine handoffs. Restart only for manual recovery or an
explicit user request. Each round must verify current STATUS, IMPL and Code Head.

Consume only bounded evidence: Task ID, STATUS, approved Plan/fast-path marker,
exact IMPL artifact, frozen Code Head, diffs/tests, and prior Review only when
re-review context requires it.

After creating REVIEW-NNN:

1. do not modify implementation code;
2. do not transition STATUS;
3. signal Lead with `madw signal review <TASK-ID> <ROUND>`;
4. stop; do not continue into fixes.
