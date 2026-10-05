# Interactive tmux team

Initialize once with this guide and `roles/<role>.md`. Later handoffs read STATUS
and only the current action's artifacts; load detailed protocol, workflow or
adapters only when needed. The Control Plane is `<project>/.agent-team/`, ignored
by Git. STATUS owns lifecycle and exact references; TASK owns requirements.
STATUS Artifact fields are filenames only; numeric Round matches the filename
suffix. History and terminal output are supporting context.

## Role boundaries

- Lead alone communicates with the user, changes STATUS and accepts tasks.
- Impl plans, implements, tests, commits and creates PLAN/IMPL evidence.
- Review verifies the exact frozen Code Head and creates REVIEW evidence.

Never run mutable Impl work and Review concurrently in one working tree.
Keep worker context across rounds; Review reloads current STATUS, IMPL, requirements
and SHA and independently verifies every round. Restart only for recovery or an
explicit reset. Old conclusions never prove a new target.

## Lead loop

Wait for user requirements, then create TASK/STATUS against a clean Git baseline.
Use SKILL's Plan Gate criteria to decide whether planning is required. Delegate
Impl's next permitted action, wait, validate its artifact and update STATUS.
Send Review the frozen IMPL/head; wait and consume REVIEW. On FAIL send confirmed
RW findings to Impl; on PASS validate acceptance and write ACCEPTANCE/STATUS.
Use direct IMPLEMENTING → REVIEWING and REVIEWING → ACCEPTED when all evidence
is available. Continue until ACCEPTED, CANCELLED, BLOCKED or a real user decision.

Interactive handoffs do not end Lead's turn. Process workers instead return to
the orchestrator after one legal action, including an intermediate Lead transition.

## Handoff and waiting

Send only Task ID, action, STATUS path, exact input artifact/head and three-digit
completion round. Do not paste plans, code or repeated protocol reminders.

```text
Task: TASK-...
Action: plan | implement | rework | review
STATUS: .agent-team/tasks/TASK-.../STATUS.md
Input: exact Plan/IMPL/Review reference, or N/A
Code Head: exact SHA for Review
Round: 001
```

Use `./.agent-team/madw send impl|review "<handoff>"`, then one
`./.agent-team/madw wait impl|review <TASK-ID> <ROUND> [timeout]`.
If the tool yields a running process, resume that same process with 30–60 second
waits. Do not start duplicate waits, capture panes or reread progress during normal
waiting. Give user updates without extra diagnostic reads. Inspect logs/panes only
after failure, timeout, abnormal notification or a user request.

Workers write the immutable artifact, run `madw signal <role> <TASK-ID> <ROUND>`
once and stop with a concise artifact/result/blocker summary. Never edit signaled
artifacts. Completion verifies identity, not acceptance; Lead validates evidence.

If unable to complete, stop and run
`madw notify <role> <TASK-ID> <ROUND> BLOCKED "<reason; needed action>"`.
Impl uses PLAN_REWORK instead for a material Plan deviation. No completion
artifact is required. `wait` returns 3 and prints the notification. Lead validates
and records it, then routes to PLAN_REWORK or BLOCKED with Resume State. Preserve
unfinished code; after resolution use a new unused round. For details load
`adapters/tmux.md → Abnormal handoffs`. Normal target mismatch still creates REVIEW.

## References and recovery

Load templates for the current action and SKILL sections for Plan Gate, lifecycle,
contract amendments or acceptance as needed. Use only artifacts referenced in
STATUS plus the single new artifact awaiting Lead consumption.

`madw send` gates UI readiness; `wait` checks completion, timeout and Agent health.
A failed query is unknown state: retain the error and recover the transport rather
than recreating the team. Load `adapters/tmux.md` for startup or transport failures.
`madw logs <role>` and `runtime/logs/events.tsv` are diagnostics, not task evidence.
`madw debug off|on` controls logging. Ctrl+C closes the project team; `stop` retains
artifacts/logs. Manual `restart <role>` is for recovery/reset.
