# tmux Adapter

tmux is the default interactive coordination layer for this Skill.

## Topology

Each Git project gets one project-scoped tmux session:

```text
madw-<repo>-<path-hash>
└── window: team
    ├── Lead   (pane)
    ├── Impl   (pane)
    └── Review (pane)
```

The path hash prevents repositories with the same basename from sharing a team.
The session records the canonical Git root and refuses to attach if the metadata
does not match the current project.

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

Runtime selection:

1. explicit `madw start pi|codex`;
2. `MADW_RUNTIME`;
3. installed `pi`;
4. installed `codex`;
5. fail before creating panes.

`start` also verifies Git, tmux, the installed Skill, and the selected runtime.
It creates the three panes only after preflight succeeds.

The launcher does not rely on a fixed one-second sleep. It verifies that each
pane/Agent process is alive, up to `MADW_BOOT_TIMEOUT` (default 15 seconds), and
fails closed if the process exits. This is intentionally **process liveness**,
not runtime-specific UI readiness detection. Add Pi/Codex-specific readiness
checks only if real startup behavior proves they are needed.

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
expected Plan/IMPL/REVIEW artifact exists.

A completion signal means "worker turn finished", not "evidence accepted".
Lead still validates the artifact before changing STATUS.

## Review freshness

```bash
madw restart review
```

This uses `tmux respawn-pane -k`, preserving the session, layout and pane
address while starting a fresh Review process/context.

A team has exactly one runtime. `madw restart <role>` always reuses the stored
team runtime/command. Runtime changes are team-level operations:

```bash
madw stop
madw start pi      # or codex
```

Per-role runtime overrides are intentionally unsupported because they would make
team-level runtime metadata ambiguous.

## Observation

```bash
madw status
madw watch
madw attach impl
madw attach review
```

`status` shows the project/team, active Task/state/head/artifacts when
available, the expected next actor, and pane process health.

`watch` attaches to the full three-pane team UI.

Terminal scrollback is observational only. Never use it as lifecycle truth.

## Extended keys

Interactive coding Agents may use modified Enter keys. If needed, add:

```tmux
set -g extended-keys on
```

to `~/.tmux.conf` and restart the tmux server when convenient.
