# Automatic Orchestration

## Goal

Remove routine human handoffs while preserving the existing protocol:

\`\`\`text
User
 ↓
Lead / Orchestrator
 ↓
Impl → Lead → Impl → Lead → Review → Lead
                     ↑             │
                     └── rework ───┘
 ↓
ACCEPTED / BLOCKED
\`\`\`

The Orchestrator is an execution mechanism, not a fourth authority.

## Why this is separate from Warp UI

Warp panes are independent terminal sessions. Synchronized input broadcasts the same input and is therefore not suitable for role-targeted dispatch.

The automation layer uses either:

- **direct transport** — Orchestrator launches fresh role workers itself;
- **queue transport** — Lead pane queues jobs and dedicated Impl/Review pane workers consume them.

Queue transport gives the desired visible three-pane experience without UI automation or keystroke injection.

## State-driven dispatch

The Orchestrator always reads STATUS before deciding what to do.

Impl/Review do not advance lifecycle state. They produce immutable artifacts. An artifact not yet referenced by STATUS indicates that Lead must consume that handoff.

Examples:

\`\`\`text
PLANNING + no new Plan
→ Impl

PLANNING + PLAN-v001 exists but STATUS still references N/A
→ Lead

IMPLEMENTING + no new IMPL
→ Impl

IMPLEMENTING + IMPL-001 exists but STATUS has not consumed it
→ Lead

REVIEWING + no new REVIEW
→ Review

REVIEWING + REVIEW-001 exists but STATUS has not consumed it
→ Lead
\`\`\`

This preserves the original Lead-only transition invariant.

## Direct mode

\`\`\`bash
agent-team --runtime codex --transport direct run TASK-...
\`\`\`

Best for CI, unattended local execution, and initial validation.

## Warp queue mode

Right-top:

\`\`\`bash
agent-team --runtime codex worker Impl
\`\`\`

Right-bottom:

\`\`\`bash
agent-team --runtime codex worker Review
\`\`\`

Left:

\`\`\`bash
agent-team --runtime codex --transport queue run TASK-...
\`\`\`

The left pane executes Lead actions directly and routes Impl/Review actions to the right panes.

## Runtime files

\`\`\`text
.agent-team/runtime/
├── workers/
│   ├── impl.json
│   └── review.json
├── queue/
│   ├── impl/
│   └── review/
├── results/
└── <TASK-ID>/
    ├── orchestrator.lock
    ├── dispatch.jsonl
    ├── lead.log
    ├── impl.log
    └── review.log
\`\`\`

These files are operational metadata only.

## Failure model

The Orchestrator is deliberately fail-closed.

It stops when:

- the Task is BLOCKED;
- the expected role worker is unavailable;
- a role run exits with an error;
- a role run produces no protocol progress;
- a human decision is required;
- the task exceeds the configured maximum number of steps.

It never invents a product decision merely to keep automation moving.

## Concurrency

One Orchestrator may control a Task at a time. A task-local lock prevents accidental duplicate orchestration.

Different Tasks may be orchestrated independently if their Code Plane changes do not conflict. The current protocol does not automatically resolve concurrent Git edits.

## Review isolation

Every Review dispatch starts a fresh runtime process/context. Review receives artifacts and repository evidence, not Impl private reasoning.

## Current scope

Implemented drivers:

- Codex: \`codex exec --full-auto\`
- Pi: RPC mode

The runtime-independent protocol remains valid for other coding agents; they need a driver that satisfies the same worker contract.
