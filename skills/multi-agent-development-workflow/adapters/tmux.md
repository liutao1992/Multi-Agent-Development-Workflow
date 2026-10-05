# tmux Adapter

tmux is the default interactive coordination layer for this Skill.

## Topology

By default each Git project gets three role sessions:

```text
madw-<repo>-<path-hash>          Lead
madw-<repo>-<path-hash>-impl     Impl
madw-<repo>-<path-hash>-review   Review
```

Each session starts in the canonical Git root. The user starts Pi or Codex in
any combination. An explicit `madw start pi|codex` keeps the earlier automatic
three-pane team for compatibility. The path hash isolates repositories with
the same name.

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

`madw start` creates shell sessions and attaches to Lead. In each session run
`madw launch pi|codex`; the command starts the chosen Agent and automatically
bootstraps Lead. Use `madw attach impl|review|leader` to enter a role session.
Direct `pi` or `codex` startup is also supported, followed by
`madw bootstrap leader` from another terminal. `madw send` prefixes
Impl/Review handoffs with their role prompt.

`madw start pi|codex` automatically starts that runtime in the old three-pane
layout. `MADW_RUNTIME` or `MADW_AGENT_CMD` also selects automatic mode. Only
this mode uses `--layout balanced|columns`, `MADW_BOOT_TIMEOUT`, and the stored
runtime command. It is retained for existing teams.

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

## Review freshness

```bash
madw restart review
```

In manual mode, `madw restart review` respawns the runtime selected by
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

`watch` attaches to Lead in manual mode and to the full three-pane UI in
automatic mode. `attach <role>` selects that role session in manual mode.
Automatic mode enables tmux mouse mode only for its team session.

Terminal scrollback is observational only. Never use it as lifecycle truth.

## Extended keys

Interactive coding Agents may use modified Enter keys. If needed, add:

```tmux
set -g extended-keys on
```

to `~/.tmux.conf` and restart the tmux server when convenient.
