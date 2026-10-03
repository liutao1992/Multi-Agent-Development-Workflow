# Codex Runtime Adapter

Core protocol is defined by SKILL.md.

## Warp mapping

- Left → Codex Lead
- Right top → Codex Impl
- Right bottom → Codex Review

## Control Plane

Do not include `.agent-team` workflow artifacts in Code Plane commits. Default to `<project-root>/.agent-team/` and exclude it from Git. Do not use `/tmp` or `/private/tmp` automatically; external Control Roots require explicit configuration.

## Review isolation

Prefer a fresh Codex Review session/context.

Give Review artifacts plus Task Baseline SHA, Previous Head SHA, and exact Code Head SHA. Do not provide Impl private reasoning as proof.

Review should inspect the exact clean Code Head snapshot and both full-task and current-round diffs.

## Subagents

Codex subagents/delegation may implement logical roles, but STATUS transitions remain Lead-controlled and protocol gates remain mandatory.

## Automatic Orchestrator driver

The bundled Orchestrator uses fresh non-interactive Codex workers:

\`\`\`bash
codex exec --full-auto "<worker prompt>"
\`\`\`

Each dispatch is a fresh execution context. This is especially important for Review independence.

Use:

\`\`\`bash
agent-team --runtime codex run <TASK-ID>
\`\`\`

For Warp three-pane routing:

\`\`\`bash
agent-team --runtime codex --transport queue run <TASK-ID>
\`\`\`
