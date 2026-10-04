# Automatic Orchestration

## Goal

The default interactive architecture is intentionally small:

```text
User
 ↓
Lead pane
 ├─ tmux → Impl pane
 └─ tmux → fresh Review pane
 ↓
ACCEPTED / BLOCKED
```

tmux provides runtime, addressed transport, synchronization and observability.
`.agent-team/` provides durable workflow state/evidence. Git HEAD identifies
the reviewed code. Lead remains the only lifecycle authority.

## Start

```bash
madw start
```

This creates one project-scoped session with Lead/Impl/Review panes and attaches
to the full team UI.

## Dispatch

Lead sends bounded notifications:

```bash
madw send impl "<Task ID + Action + STATUS/artifact references>"
madw wait impl TASK-... 001
```

Review:

```bash
madw restart review
madw send review "<Task ID + exact IMPL/head + STATUS references>"
madw wait review TASK-... 001
```

Impl/Review write immutable artifacts first, then signal with `madw signal`.

The signal is only synchronization. Lead still applies all Plan Gate, Task
Contract, Code Head, Review result, rework and acceptance rules before advancing
STATUS.

## Failure model

`madw wait` fails closed on timeout, pane/process death, or missing expected
artifact and captures recent pane output to aid diagnosis.

The workflow also stops when STATUS is BLOCKED, a role violates its write
boundary, the Review target is invalid, or a genuine product decision is needed.

## Review independence

Use `madw restart review` before each substantive Review round. It uses
`tmux respawn-pane -k`, keeping pane identity/layout stable while replacing the
Review Agent context.

## Process fallback

CI and unattended runs may continue to use:

```bash
agent-team --runtime codex --transport process run <TASK-ID>
agent-team --runtime pi --transport process run <TASK-ID>
```

The Python fallback mechanically enforces state transitions and postconditions.
It is not the communication layer for the interactive tmux team.

## Removed Queue transport

The old filesystem queue, worker heartbeat, lease/claim/quarantine protocol and
`agent-team worker Impl/Review` commands are removed. Do not recreate
`.agent-team/runtime/` as an Agent message bus.

## Concurrency

One mutable automated Task per Git working tree. Use Git worktrees for parallel
Tasks.
