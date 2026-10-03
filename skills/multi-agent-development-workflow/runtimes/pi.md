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

## Automatic Orchestrator driver

The bundled Orchestrator starts Pi in RPC mode for each dispatched role action:

\`\`\`bash
pi --mode rpc --no-session --approve
\`\`\`

The worker prompt is sent through the RPC \`prompt\` command and the Orchestrator waits for \`agent_settled\`.

Each Review dispatch uses a fresh Pi process/context.

Use:

\`\`\`bash
agent-team --runtime pi run <TASK-ID>
\`\`\`

For Warp three-pane routing:

\`\`\`bash
agent-team --runtime pi --transport queue run <TASK-ID>
\`\`\`
