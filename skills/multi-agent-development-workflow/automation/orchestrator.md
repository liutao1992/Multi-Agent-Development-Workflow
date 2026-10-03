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

A quarantine represents `UNKNOWN_ORPHAN_RISK` or `UNKNOWN_PROCESS_IDENTITY`. New automated Task runs and queue workers fail closed until it is inspected/resolved; the runtime never blindly retries that job.

Quarantine also writes an orphan-risk marker in the worktree's Git directory. This blocks runs using alternate Control Roots until the claim and process are inspected, quiesced, and both markers are cleared.

A stale live PID is never treated as sufficient identity by itself. The claim records process identity metadata when the child starts. Recovery compares that identity before terminating a live process. PID reuse therefore causes quarantine rather than a kill.

If a sandbox denies `ps`, failed or empty inspection is never evidence that a live child has stopped. Recovery/cancellation quarantines claims whose identity cannot be verified, and keeps the shared orphan-risk marker until inspected. Run orphan inspection and recovery in an environment that permits process inspection.

The two real-process integration tests probe `ps` access independently and report SKIPPED in restricted environments. Permission-denial behavior is covered by deterministic unit tests. CI sets `AGENT_TEAM_REQUIRE_PROCESS_INSPECTION=1` so missing process-inspection access fails the suite instead of skipping those integration tests.

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

## Requirement snapshot binding

The runtime treats TASK requirements as a versioned contract, not mutable background text.

```text
TASK Contract Revision + SHA-256
       ↓
PLAN
       ↓
IMPL
       ↓
REVIEW
       ↓
ACCEPTANCE
```

All active evidence must bind the same revision/hash.

A Lead requirement amendment must increment the revision, record previous/new hashes in the Requirement Change Log, and—once any Plan/IMPL/Review exists—return the workflow to `PLAN_REWORK`.

This prevents an already-reviewed Code Head from being accepted against silently rewritten requirements.

`Rework Requirements` contains Review remediation instructions and is excluded from the requirement hash. Lead may update only that TASK section during `REVIEWING -> REWORK`, with valid FAIL or MISMATCH evidence. Contract revision/hash and all other TASK content remain unchanged. Product requirement changes still require a contract amendment and `PLAN_REWORK`.

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
  require current Git HEAD == reviewed/accepted Code Head

<any> → BLOCKED
  require Resume State == prior state
```

Review/implementation snapshot SHAs used as authoritative targets must be full 40-character Git SHAs.

Review evidence is machine-checked for PASS, FAIL and REVIEW_TARGET_MISMATCH.

- PASS: exact current IMPL/head, READY_FOR_REVIEW protocol, clean checks, matching Task Contract.
- FAIL: same target checks, STATUS/artifact both FAIL, and at least one blocking REV issue.
- MISMATCH: Result N/A, protocol mismatch in STATUS/artifact, submitted Declared Head and current Observed Head verified.

The same reviewed HEAD and Task Contract are checked again during final acceptance to prevent Code and Requirement TOCTOU gaps.

Plan approval is field-scoped while pending: Lead may mutate only the current Plan's `## Approval` block during PLAN_REVIEW. After APPROVED or REWORK is recorded, the whole Plan version is immutable.

If the Task Contract changes during `PLAN_REVIEW`, Lead enters `PLAN_REWORK` and leaves the old pending Plan unchanged. Its revision/hash remain historical evidence. Impl then creates the next Plan version against the new contract; this path does not require a REWORK approval on the invalidated Plan.

## Failure model

The Orchestrator is deliberately fail-closed.

Before dispatch, it writes a `runtime/tasks/<task-id>/pending-validation.json` marker. The marker is removed only after the worker result passes all protocol checks. A failed or interrupted step leaves it in place, and later `run`/`resume` attempts stop before dispatch. Inspect the worker and its artifacts, quiesce any child process, and reconcile the Task before manually clearing the marker. An `ACCEPTED` state is also checked against current implementation, Review, acceptance artifact, and Git HEAD on each run.

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

The lock lives in the worktree's Git directory, so alternate Control Roots for the same worktree contend on the same file.

Even disjoint file edits cannot safely share a working tree because Git HEAD and index are shared.

Parallel Tasks require separate Git worktrees. Worktree-native parallel orchestration is the intended future concurrency model.

## BLOCKED recovery

Ordinary `run` treats BLOCKED as a stop condition.

After a human resolves the dependency:

```bash
agent-team --runtime codex resume TASK-... "human decision"
```

The resume command runs exactly one Lead recovery transition, persists the human decision in STATUS → Blocked Resolution, verifies `BLOCKED → Resume State`, and then re-enters normal automatic execution.

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
