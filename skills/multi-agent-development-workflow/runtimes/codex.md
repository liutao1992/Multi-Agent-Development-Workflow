# Codex Runtime Adapter

Core protocol is defined by SKILL.md.

## tmux-native mode

```bash
madw start codex
```

Lead, Impl and Review run in one project-scoped tmux session. Use tmux-native
handoffs/synchronization rather than a project-defined Queue.
MADW launches Codex in `workspace-write` with
`sandbox_workspace_write.network_access=true` by default so its macOS shell
commands can reach the tmux Unix socket on the first attempt. This also
permits broader outbound network access from commands run by that team's
Agents; MADW does not change global Codex configuration. Select the
restrictive policy explicitly with
`MADW_CODEX_NETWORK_ACCESS=0 madw start codex`, which forces
`network_access=false`. `MADW_AGENT_CMD` overrides the generated command
when a custom policy is required.

For an existing Codex team, install the accepted Skill version first, then
run `MADW_CODEX_NETWORK_ACCESS=1 MADW_NO_ATTACH=1 madw start codex`.
This updates only the stored startup command. Restart Review and Impl after
their current handoffs, then restart Lead from a safe external control point;
each role adopts the new command only after its restart. The tmux session,
pane arrangement, and `.agent-team/` evidence remain in place. A restrictive
or externally constrained sandbox may still require elevation for the one
MADW command that failed.

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
