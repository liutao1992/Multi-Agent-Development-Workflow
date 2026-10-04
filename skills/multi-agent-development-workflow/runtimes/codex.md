# Codex Runtime Adapter

Core protocol is defined by SKILL.md.

## tmux-native mode

```bash
madw start codex
```

Lead, Impl and Review run in one project-scoped tmux session. Use tmux-native
handoffs/synchronization rather than a project-defined Queue.

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
