# Interactive tmux team

Read this guide and `roles/<role>.md` at role initialization. Keep them in the
Agent's context. On later handoffs read the current Task's STATUS and only the
artifacts required by that action. Do not reload the entire SKILL on every turn.

## Workspace and roles

One project-scoped tmux session contains Lead, Impl and Review panes. Users
choose Pi or Codex in each pane. `madw launch` records that choice; direct
startup works but requires `madw bootstrap leader` from another terminal.
The compatibility option `madw start --sessions` uses separate role sessions.

- Lead alone communicates with the user, owns STATUS and decides acceptance.
- Impl plans, implements, tests, commits and creates Plan/IMPL artifacts.
- Review independently checks the specified implementation and creates REVIEW.
- Impl and Review never change STATUS or impersonate another role.

The Control Plane is `<project>/.agent-team/`, ignored by Git. Read STATUS first
and use its exact references. History and terminal output are background only.

## Lead loop

Wait for a user requirement before creating a Task. Then:

1. Create TASK/STATUS against a clean Git baseline. For a small, understood
   change apply the existing Plan Gate criteria before adding a planning round.
2. Send Impl the next permitted planning, implementation or rework action.
3. Wait for its completion signal, inspect its artifact, and update STATUS.
4. Send Review the exact frozen IMPL and Code Head; wait and inspect its REVIEW.
5. On FAIL send confirmed findings back to Impl. On PASS verify acceptance and
   record ACCEPTANCE/STATUS. Combine adjacent permitted Lead decisions when
   their evidence is already available.
6. Continue until ACCEPTED, CANCELLED, BLOCKED, or a real user decision is needed.

A worker handoff is a delegation boundary, not a reason for interactive Lead
to end its turn. Only Process Orchestrator workers stop after one action.

## Handoff format

Send only Task ID, action, STATUS path, exact input artifact/head and a three-digit
completion round. Do not paste complete plans, source files or protocol rules.

```text
Task: TASK-...
Action: plan | implement | rework | review
STATUS: .agent-team/tasks/TASK-.../STATUS.md
Input: exact Plan/IMPL/Review reference, or N/A
Code Head: exact SHA for Review, otherwise as required
Round: 001
```

Lead uses `./.agent-team/madw send impl|review "<handoff>"`, then
`./.agent-team/madw wait impl|review <TASK-ID> <ROUND> [timeout]`.
Workers write the required artifact and call
`./.agent-team/madw signal impl|review <TASK-ID> <ROUND>` once. Report only the
artifact, result and unresolved blocker; Lead owns the user-facing summary.

Completion signals verify artifact identity, not acceptance. Never edit an
artifact after signaling it. Do not run mutable Impl work and Review together
in the same working tree.

## Review continuity

Keep Review running across rounds. Do not restart it automatically. Each round
reload current STATUS, the specified IMPL, requirement snapshot and Code Head;
verify the current checkout and tests independently. Previous findings help
re-review but never replace evidence for the new round. Manual reset is for
user-requested recovery; `madw restart review` discards the old context.

## Read detailed references only when needed

- New task: `templates/TASK.md`, `templates/STATUS.md`, and SKILL's Plan Gate
  classification, task contract and lifecycle table.
- Planning: the Plan template and the current TASK/STATUS.
- Implementation/rework: approved Plan or fast path, confirmed Review findings,
  and the IMPL template.
- Review: exact IMPL/head, current TASK/STATUS, relevant Plan and REVIEW template.
- Acceptance or contract change: the corresponding SKILL rules and template.

## Transport and diagnostics

`madw send` gates input on UI readiness; `wait` detects the supported Agent
leaving its UI even when its pane returns to a shell. Query errors mean unknown
state: retain the error and retry or elevate that command, never recreate a
team merely because a query failed. Codex sandbox/socket details are in
`adapters/tmux.md` and README; load them only on a transport failure.

Debug mode records role terminal streams and `runtime/logs/events.tsv`. Events
include time, action, role, Task/round when supplied, wait duration, prompt
character count and result. They are diagnostics, not workflow evidence.
`madw debug off` disables both log types; `on` resumes appending.

Ctrl+C closes the entire project team. Use manual `restart <role>` only for
recovery or an explicit reset. `stop` preserves the Task artifacts and logs.
