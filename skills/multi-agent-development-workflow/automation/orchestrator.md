# Automatic Orchestration

## Goal

Remove routine human handoffs while preserving the existing protocol. **Native SubAgent orchestration is preferred; the standalone script is a fallback when the parent runtime cannot expose subagent primitives:**

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

In native mode, Lead itself is the parent Orchestrator. In standalone mode, `scripts/orchestrator.py` is only a transport fallback.

## Why this is separate from Warp UI

Warp panes are independent terminal sessions. Synchronized input broadcasts the same input and is therefore not suitable for role-targeted dispatch.

The automation layer uses either:

- **process transport** — Orchestrator launches fresh role workers itself;
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

## Process fallback mode

\`\`\`bash
agent-team --runtime codex --transport process run TASK-...
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

## Queue lifecycle

Queue transport uses explicit job state and lease semantics:

```text
QUEUED
→ CLAIMED
→ RUNNING + renewable lease
→ SUCCEEDED / FAILED / CANCELLED
```

On orchestrator timeout, a cancellation marker is written. Before the orchestrator releases control, it attempts to quiesce any claimed child process recorded for that job. Running workers also observe cancellation and terminate the child process group.

Expired claims are requeued only when a recorded child PID can be confirmed quiesced. If the PID was never durably recorded, the claim is malformed, or the child cannot be confirmed stopped, the claim moves to `quarantined/` with an error record.

A quarantine represents `UNKNOWN_ORPHAN_RISK`. New automated Task runs and queue workers fail closed until it is inspected/resolved; the runtime never blindly retries that job.

Every job is project-scoped and carries both canonical project root and project fingerprint.

## Role enforcement

Process/Queue fallback validates pre/post conditions in code, not only prompts. A role that mutates forbidden state causes orchestration to stop.

The validator snapshots the whole durable project Control Plane (excluding `runtime/`). This protects `INDEX.md` and every other Task namespace, not just the current Task.

The allowed write set is role-scoped:

```text
Lead
  current Task Lead-owned data + INDEX

Planning Impl
  current Task / plans / exactly one new PLAN

Implementation Impl
  current Task / implementations / exactly one new IMPL
  + permitted Code Plane implementation

Review
  current Task / reviews / exactly one new REVIEW
```

Other Task namespaces are immutable to the active role.

## Executable lifecycle transitions

After every Lead action, `state_machine.py` validates both transition legality and evidence.

Examples:

```text
CREATED → ACCEPTED
  reject

PLAN_REVIEW → READY_FOR_IMPLEMENTATION
  require Plan APPROVED in STATUS + Plan artifact

REVIEWING → READY_FOR_FINAL_ACCEPTANCE
  require current REVIEW PASS

READY_FOR_FINAL_ACCEPTANCE → ACCEPTED
  require ACCEPTANCE.md
  require current Review PASS
  require accepted Code Head == current implementation Code Head

<any> → BLOCKED
  require Resume State == prior state
```

Review/implementation snapshot SHAs used as authoritative targets must be full 40-character Git SHAs.

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

Two locks are used:

1. **Code Plane lock** — one automated Task per Git working tree.
2. **Task lock** — prevents duplicate orchestration of the same Task.

The Code Plane lock is deliberately **fail-closed**. If its owner process is gone, it is not automatically stolen because an orphan worker/child process may still be mutating the working tree. Inspect and quiesce leftovers before removing a stale Code Plane lock.

Even disjoint file edits cannot safely share a working tree because Git HEAD and index are shared.

Parallel Tasks require separate Git worktrees. Worktree-native parallel orchestration is the intended future concurrency model.

## Review isolation

Every Review dispatch starts a fresh runtime process/context. Review receives artifacts and repository evidence, not Impl private reasoning.

## Current scope

Implemented drivers:

- Codex: \`codex exec --full-auto\`
- Pi: RPC mode

The runtime-independent protocol remains valid for other coding agents; they need a driver that satisfies the same worker contract.


## Preferred native mode

See [Native SubAgent Orchestration](./subagent.md).

The standalone script cannot reach into an already-running parent session and call that session's native subagent collaboration tools. Do not label a separate \`codex exec\` or Pi RPC process as a SubAgent.

Use native mode from the Lead parent session when the runtime exposes subagents; use this script only as fallback.
