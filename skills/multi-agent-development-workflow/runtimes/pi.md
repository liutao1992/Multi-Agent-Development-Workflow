# Pi Runtime Adapter

Core protocol is defined by SKILL.md.

## tmux-native mode

```bash
madw start
# or explicitly
madw start pi
```

The launcher creates one project-scoped tmux session with Pi Lead, Impl and
Review panes. Lead communicates through tmux; there is no filesystem Queue
transport.

Review is refreshed per round with:

```bash
madw restart review
```

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
