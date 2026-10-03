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

## Native SubAgents — preferred

When the current Codex host exposes multi-agent tools, use them as the preferred execution transport.

Codex multi-agent configuration supports enabling agents and declaring custom agent roles. The runtime should map:

\`\`\`text
Parent / Root → Lead
Impl child    → roles/impl.md
Review child  → roles/review.md
\`\`\`

STATUS transitions remain Lead-controlled and all protocol gates remain mandatory.

Impl should normally be reused within a Task.

Review must be freshly spawned for every Review round and must not inherit Impl private reasoning.

The exact collaboration primitive names depend on the Codex host/version. Use the runtime-provided create/spawn, message/follow-up, wait, interrupt/close operations rather than shelling out when those native primitives are available.

## Process fallback driver

The bundled standalone Orchestrator is the fallback when the current Lead session cannot use native SubAgents. It uses non-interactive Codex worker processes:

\`\`\`bash
codex exec --full-auto "<worker prompt>"
\`\`\`

This is a process fallback, not a native SubAgent. Each Review dispatch is fresh to preserve Review independence.

Use:

\`\`\`bash
agent-team --runtime codex run <TASK-ID>
\`\`\`

For Warp three-pane routing:

\`\`\`bash
agent-team --runtime codex --transport queue run <TASK-ID>
\`\`\`
