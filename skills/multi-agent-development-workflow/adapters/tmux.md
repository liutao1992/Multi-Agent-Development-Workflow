# tmux Adapter

tmux is the default interactive coordination layer for this Skill.

## Topology

By default each Git project gets one session with three side-by-side role panes:

```text
madw-<repo>-<path-hash>          Lead | Impl | Review
```

Each pane starts in the canonical Git root. The user starts Pi or Codex in any
combination. `madw start --sessions` retains the previous three independent
role sessions when needed. An explicit `madw start pi|codex` starts the same
runtime automatically in all three panes. The path hash isolates repositories
with the same name.

## Responsibilities

```text
Skill       = protocol
tmux        = runtime + addressed transport + synchronization + observability
.agent-team = durable state + evidence
Git HEAD    = code identity
```

Do not add another mailbox/queue/inbox/outbox layer for interactive Agents.

## Startup

```bash
madw start
```

`madw start` creates three shell panes and attaches to Lead. In each pane run
`madw launch pi|codex`; the command starts the chosen Agent and automatically
bootstraps Lead. Use `madw attach impl|review|leader` to focus a role pane.
Direct `pi` or `codex` startup is also supported, followed by
`madw bootstrap leader` from another terminal. `madw send` prefixes
Impl/Review handoffs with their role prompt.

`madw start pi|codex` automatically starts that runtime in three panes.
`MADW_RUNTIME` or `MADW_AGENT_CMD` also selects automatic mode. The default
layout is three columns; `--layout balanced` puts Lead on the left and stacks
Impl/Review on the right. Automatic mode also uses `MADW_BOOT_TIMEOUT` and the
stored runtime command.

The launcher does not rely on a fixed one-second sleep. It verifies that each
pane/Agent process is alive, up to `MADW_BOOT_TIMEOUT` (default 15 seconds), and
fails closed if the process exits. Process liveness alone is not input
readiness: after a respawn, Pi and Codex spend a while initializing and then
redraw a full-screen UI that silently discards any input pasted before the UI
is ready (the pre-UI terminal echoes the paste and the redraw erases it). For
the supported TUI runtimes, `start`, `madw restart <role>`, and `madw send`
wait for the pane to enter the terminal alternate screen — the signal that the
Agent UI is ready to receive a handoff — up to `MADW_TUI_TIMEOUT` (default 10
seconds). If the UI never appears, the command fails without sending the
handoff. Without this gate a handoff sent right after `madw restart review`
never reaches Review, and Lead's retries look like inexplicable Review agent
restarts. Custom `MADW_AGENT_CMD` agents keep liveness-only waiting unless
`MADW_TUI_READY=1` opts the team into the same alternate-screen gate.

## Sending handoffs

Prefer the launcher wrapper because it uses tmux buffers for multiline-safe
delivery:

```bash
madw send impl "<bounded handoff>"
madw send review "<bounded handoff>"
```

Keep the handoff thin: Task ID, Action, STATUS path, exact artifact references,
and completion round. The worker reads authoritative context from the Control
Plane.

## Synchronization

Lead uses timeout/death-aware waiting:

```bash
madw wait impl TASK-... 001
madw wait review TASK-... 001
```

The worker signals only after its immutable artifact is durably written:

```bash
madw signal impl TASK-... 001
madw signal review TASK-... 001
```

Internally this uses `tmux wait-for`, while `madw wait` also detects a dead
pane, enforces a timeout, captures recent output on failure, and verifies the
expected Plan/IMPL/REVIEW artifact exists. The completion hash is kept in the
project's tmux session, so repeating a wait after interruption verifies the
same immutable artifact instead of waiting forever.

A completion signal means "worker turn finished", not "evidence accepted".
Lead still validates the artifact before changing STATUS.

## Review continuity and manual recovery

Review keeps its Agent context across rounds. Each handoff points to current
STATUS, exact IMPL and Code Head; previous findings are background for re-review.
Do not restart Review for routine handoffs. If the user explicitly requests a
reset, or a role needs recovery, use:

```bash
madw restart review
```

For that manual reset, `madw restart review` respawns the runtime selected by
`madw launch`. A directly started Review Agent has no stored command, so the
session resets to a shell and the user starts an Agent again. The pane address
and completion metadata stay stable. In automatic mode the command respawns
the team runtime.

## Observation

```bash
madw status
madw watch
madw attach impl
madw attach review
```

`status` shows the project/team, active Task/state/head/artifacts when
available, the expected next actor, and pane process health.

`watch` attaches to Lead. `attach <role>` focuses that role's pane in the
default layout, or switches sessions with `--sessions` teams. Mouse selection
is enabled for pane teams.

Each role's terminal stream is appended to
`.agent-team/runtime/logs/<role>.log`. Inspect recent output with
`madw logs review 200`; the default is 120 lines. `madw logs` removes terminal
color and cursor control sequences for readable output. Debug logging is on
for new teams; toggle it with `madw debug off|on`.

Debug mode also appends structured events to `.agent-team/runtime/logs/events.tsv`:
UTC timestamp, event, role, Task, round, elapsed seconds, prompt characters and
result. Startup/exit, role initialization, send/failure, wait/completion/failure,
manual restart and signal are recorded without message contents. Send has no
explicit round argument, so its round is `-`; wait/signal carry the exact round.
Repeated sends are observable attempts, not automatic retry counts. Character
counts are not model Token usage. Debug off disables both event and terminal logs.

Terminal scrollback is observational only. Never use it as lifecycle truth.

## Ending the team

Press `Ctrl+C` directly in any role pane, without the tmux prefix, or run
`madw stop`. Both close the current project's whole team and its Agent
processes. With `--sessions`, all three role sessions close together. The key
binding is scoped to the team's sessions; other projects keep running.

## Extended keys

Interactive coding Agents may use modified Enter keys. If needed, add:

```tmux
set -g extended-keys on
```

to `~/.tmux.conf` and restart the tmux server when convenient.

## Abnormal handoffs

A worker unable to produce valid completion evidence must stop and notify:

```bash
madw notify impl <TASK-ID> <ROUND> PLAN_REWORK "<material deviation; decision needed>"
madw notify impl <TASK-ID> <ROUND> BLOCKED "<dependency; what unblocks work>"
madw notify review <TASK-ID> <ROUND> BLOCKED "<environment blocker; needed action>"
```

No completion artifact is required. A notification is saved under
`.agent-team/runtime/notifications/`, hash-checked and wakes the same wait channel.
`wait` returns 3 and prints the notification, including for an early/repeated wait.
It never treats it as successful completion or changes STATUS. Lead validates the
reason, records it in STATUS history, and routes material deviation to PLAN_REWORK
or a dependency blocker to BLOCKED with Resume State. Preserve unfinished code;
do not fabricate IMPL evidence or silently discard work. Resolve it before freezing
another review target. After resolution issue a new unused completion round;
the old round remains closed. Normal REVIEW_TARGET_MISMATCH still produces REVIEW.
