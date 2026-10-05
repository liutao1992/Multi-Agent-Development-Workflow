# Pi Runtime Adapter

Core protocol is defined by SKILL.md.

## tmux-native mode

```bash
madw start
# or explicitly
madw start pi
```

The launcher creates one project-scoped tmux session with Lead, Impl and
Review panes. Default startup leaves shells for user-selected Agents;
`madw start pi` automatically starts Pi in all three panes. Lead communicates through tmux; there is no filesystem Queue
transport.

Keep Review running across rounds. Re-read current STATUS, IMPL and Code Head
and independently verify each round. `madw restart review` is only for manual
recovery or an explicit reset; it discards context.

STATUS and immutable artifacts remain authoritative.

## Control Plane

Keep `.agent-team/` outside reviewed Code Plane history. Default to
`<project-root>/.agent-team/`.

## Process fallback

For CI/unattended execution:

```bash
agent-team --runtime pi --transport process run <TASK-ID>
```

`AGENT_TEAM_PI_MODEL` and `AGENT_TEAM_PI_THINKING` may configure that
standalone fallback.
