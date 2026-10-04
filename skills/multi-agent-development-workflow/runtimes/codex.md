# Codex Runtime Adapter

Core protocol is defined by SKILL.md.

## tmux-native mode

```bash
madw start codex
```

Lead, Impl and Review run in one project-scoped tmux session. Use tmux-native
handoffs/synchronization rather than a project-defined Queue.
Codex's default macOS shell sandbox may deny the tmux Unix socket. Operators
can explicitly opt in for one team with
`MADW_CODEX_NETWORK_ACCESS=1 madw start codex`. This uses workspace-write
with network access and also permits network access from agent commands.
`MADW_AGENT_CMD` overrides the runtime command when a different policy is
required.

Refresh Review before every substantive round:

```bash
madw restart review
```

## Control Plane

Keep `.agent-team/` excluded from reviewed Code Plane history.

## Process fallback

For CI/unattended execution:

```bash
agent-team --runtime codex --transport process run <TASK-ID>
```

This is a separate headless fallback, not the interactive team's message
transport.
