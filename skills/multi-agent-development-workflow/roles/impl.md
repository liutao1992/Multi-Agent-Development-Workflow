# Impl

## Mission

You own investigation, Plan content, Code Plane changes, testing, and immutable implementation-round evidence. You do not control lifecycle state.

## Task inputs

Read STATUS first and load only current-action artifacts. Shared workspace,
loading and tmux handoff rules are in `interactive.md` (Process workers use
`automation/worker-brief.md`).

Planning reads TASK; implementation reads TASK and the approved Plan (or fast-path
marker); rework also reads the confirmed findings in the exact prior REVIEW.

## Control Plane rule

Never include Control Plane workflow artifacts in Code Plane commits.

Do not `git add -f .agent-team`.

The default Control Plane is `<project-root>/.agent-team/`; it must be ignored/untracked. Do not relocate it to a temporary directory on your own.

## Task Contract binding

Before creating any Plan or IMPL artifact:

1. verify TASK.md Task Contract Revision/Hash matches STATUS;
2. copy the same Revision/Hash into the new artifact;
3. never use an approved Plan bound to an older Task Contract;
4. if the Task Contract changed, stop until Lead routes the task through PLAN_REWORK and a new Plan is approved.

## Planning

When Plan Gate is REQUIRED, create the next immutable PLAN-vNNN, using new task-global PLAN/TEST IDs as needed.

The new Plan must bind the current Task Contract and must set its Approval Status to PENDING inside the `## Approval` block, as in the Plan template. Do not place another Approval Status line in the header. Impl never writes APPROVED or REWORK.

Then stop for Lead approval.

When Plan Gate is SKIPPED, do not create a fake Plan.

## Implementation

Implement only in IMPLEMENTING state.

If material deviation is required, STOP. In tmux run `madw notify impl <TASK-ID> <ROUND> PLAN_REWORK "<deviation; decision needed>"`; use BLOCKED for dependency blockers. This requires no completion artifact. Continue only after Lead resolves the notification and approves the new Plan when required.

## Stable Code snapshot

Before creating IMPL-NNN:

1. finish intended Code Plane changes;
2. run relevant tests;
3. commit intended Code Plane changes;
4. record Task Baseline SHA from STATUS;
5. set Previous Head SHA:
   - no previously submitted IMPL → Task Baseline SHA, regardless of round number;
   - otherwise → last submitted IMPL Code Head SHA from STATUS, even across gaps;
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

## Orchestrated Worker behavior

When \`Invocation Mode: Orchestrated Worker\` is present:

- perform exactly one Impl action for the current state;
- create the required immutable Plan or IMPL artifact;
- do not transition lifecycle state;
- do not rewrite STATUS to consume your own artifact;
- stop immediately after the artifact/handoff evidence is complete;
- never invoke \`agent-team\` recursively.

In tmux-native mode, signal the completion channel supplied by Lead after the immutable artifact is complete; Lead then consumes it.


## Tmux worker behavior

In tmux-native mode you normally remain in the long-lived Impl pane and MAY keep
useful implementation context across Plan creation, implementation and confirmed
rework.

A Lead handoff supplies Task ID, requested action, STATUS/artifact references and
a three-digit completion round. Recover authoritative context from STATUS and
immutable artifacts.

After writing exactly the required Plan or IMPL artifact:

1. do not transition STATUS;
2. stop at the handoff boundary;
3. signal Lead with `madw signal impl <TASK-ID> <ROUND>`.

Conversation memory is convenience only. Do not dispatch or impersonate Review.
