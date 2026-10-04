# Pi Runtime Adapter

Core protocol is defined by SKILL.md.

## Warp mapping

- Left → Pi Lead
- Right top → Pi Impl
- Right bottom → Pi Review

## Control Plane

Keep workflow artifacts outside reviewed Code Plane history. Default to `<project-root>/.agent-team/` and exclude it from Git. Do not use `/tmp` or `/private/tmp` automatically; external Control Roots require explicit configuration.

## Code Mode

Code Mode may improve tool orchestration but does not replace lifecycle, Plan Gate, stable Code snapshots, independent Review, or Lead acceptance.

## Review isolation

Prefer a fresh Pi Review session/context.

Share artifacts plus Task Baseline SHA, Previous Head SHA, exact Code Head SHA, diffs, and test evidence. Do not share Impl private reasoning as proof.

## RPC / SDK

Automation must restore workflow from STATUS for existing tasks, obey the Transition Table, keep Control Plane separate, and create a new round after every submitted Code Plane change.

## Process fallback driver

The bundled standalone Orchestrator uses Pi RPC as a process fallback. If a Pi host/extension exposes true native child-agent primitives, prefer those and apply the same Lead-parent / reusable-Impl / fresh-Review policy:

\`\`\`bash
pi --mode rpc --no-session --approve --no-extensions --skill <installed-skill-directory>
\`\`\`

The worker prompt is sent through the RPC \`prompt\` command and the Orchestrator waits for \`agent_settled\`.

Each fallback Review dispatch uses a fresh Pi process/context.

`AGENT_TEAM_PI_MODEL` and `AGENT_TEAM_PI_THINKING` optionally select a Pi model
and thinking level for unattended runs; otherwise Pi uses its own defaults.

Use:

\`\`\`bash
agent-team --runtime pi run <TASK-ID>
\`\`\`

For Warp three-pane routing:

\`\`\`bash
agent-team --runtime pi --transport queue run <TASK-ID>
\`\`\`
