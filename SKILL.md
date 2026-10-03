---
name: multi-agent-development-workflow
description: Use for non-trivial software-development tasks that need multi-agent coordination, task definition, plan approval, implementation, independent review, rework, stable Git review snapshots, and final acceptance across Codex, Pi, Warp, or other coding-agent environments.
---

# Multi-Agent Development Workflow

## Purpose

This skill defines a deterministic, runtime-independent development protocol using three logical roles:

1. **Lead Agent** — requirements, lifecycle control, plan approval, rework decisions, final acceptance.
2. **Implementation Agent** — investigation, planning, implementation, testing, immutable implementation-round evidence.
3. **Review Agent** — fresh-context independent verification of a stable Git snapshot.

Only the Lead Agent may declare a task **ACCEPTED**.

Warp is the preferred interactive terminal adapter. Codex, Pi, and other coding agents are runtime adapters. Neither terminal nor runtime may redefine the protocol.

## Invocation protocol

When this skill is invoked, execute this bootstrap before task work:

1. Determine invocation mode: new task; planning / plan rework; implementation / implementation rework; review / re-review; or final acceptance.
2. Determine the acting role: Lead, Implementation, or Review. If the request is general orchestration and no role is explicit, use Lead.
3. Determine the exact Task ID and task directory.
   - Prefer an explicitly supplied Task ID.
   - If exactly one active task exists, it may be selected from `.agent-team/INDEX.md`.
   - If multiple active tasks exist, never infer which one is intended.
4. Determine workflow: `bugfix`, `standard`, or `complex`.
5. Determine runtime: Codex, Pi, or generic.
6. Load the matching role file, workflow file, runtime adapter, and `adapters/warp.md` when Warp is used.
7. Read the task's `STATUS.md` before acting.
8. Perform only actions allowed by the current lifecycle state.
9. After a lifecycle transition, update `STATUS.md` first, then refresh the derived `INDEX.md`.

## Core rule

Never collapse these questions:

- **What should be built?** → Lead
- **How should it be built?** → Implementation
- **Was it built correctly?** → Review

Implementation cannot approve itself.
Review cannot redefine requirements.
Only Lead can accept.

## Task workspace

```text
.agent-team/
├── INDEX.md
└── tasks/
    └── TASK-YYYYMMDD-NNN-short-name/
        ├── TASK.md
        ├── STATUS.md
        ├── plans/
        │   ├── PLAN-v001.md
        │   └── PLAN-v002.md
        ├── implementations/
        │   ├── IMPL-001.md
        │   └── IMPL-002.md
        ├── reviews/
        │   ├── REVIEW-001.md
        │   └── REVIEW-002.md
        └── ACCEPTANCE.md
```

Do not overwrite prior plan, implementation, or review rounds.

## Single-source-of-truth model

Authoritative mapping:

- `TASK.md` = **requirement source of truth**.
- approved `PLAN-vNNN.md` = **implementation-intent source of truth**.
- Git `Head SHA` = **implementation source of truth** for an implementation round.
- `REVIEW-NNN.md` = **verification evidence** for its exact review target.
- `STATUS.md` = **only lifecycle source of truth**.
- `ACCEPTANCE.md` = **final closure evidence**.
- `INDEX.md` = **derived dashboard only**; never overrides STATUS.md.
- conversation history = supporting context only.

Artifact-local fields such as Plan Approval Status, Implementation Result, or Review Result describe that artifact only; they do not override `STATUS.md`.

## Lifecycle states

```text
CREATED
PLANNING
PLAN_REVIEW
PLAN_REWORK
READY_FOR_IMPLEMENTATION
IMPLEMENTING
READY_FOR_REVIEW
REVIEWING
REWORK
READY_FOR_FINAL_ACCEPTANCE
ACCEPTED
BLOCKED
CANCELLED
```

Only Lead normally transitions lifecycle state.

## Artifact history

Plan, implementation, and review artifacts are append-only by version/round:

- `PLAN-v001.md`, `PLAN-v002.md`, ...
- `IMPL-001.md`, `IMPL-002.md`, ...
- `REVIEW-001.md`, `REVIEW-002.md`, ...

Never edit an old artifact into a new version/round.
`STATUS.md` and `INDEX.md` are mutable projections.
`TASK.md` may be amended only by Lead with changes explicitly recorded.

## Stable identifiers

Use:
- Requirements: `REQ-001`
- Acceptance criteria: `AC-001`
- Plan steps: `PLAN-001`
- Implementation changes: `CHANGE-001`
- Tests: `TEST-001`
- Review findings: `REV-001`
- Rework items: `RW-001`

## Plan ownership and approval

Responsibilities are split:

- **Plan Content Owner:** Implementation Agent.
- **Plan Approval Owner:** Lead Agent.

Implementation creates `PLAN-vNNN.md` with Approval Status `PENDING`.
Lead may modify only its Approval block to record `APPROVED` or `REWORK`, reviewer, date, and notes.

Once Lead records a decision, freeze that plan version. Plan rework creates the next version.

## Plan gate classification

A task may skip the Plan Gate only when it is **trivial and low-risk**.

A task is trivial only if **ALL** are true:

- change is localized;
- no database/schema/data migration;
- no public API or contract change;
- no security/auth/permission impact;
- no concurrency or synchronization impact;
- no architecture-boundary change;
- no cross-module behavioral change;
- low regression risk;
- easily reversible;
- expected implementation is small and directly understood from existing code.

If any condition is false or uncertain, require Plan approval.

Skipping the Plan Gate does not skip Review, stable Review Target, or final acceptance.

## Material plan deviation

A deviation is material when it changes an approved architecture/component boundary, API/data/schema contract, security/concurrency behavior, requirement scope, major data/state flow, migration/rollback strategy, test strategy in a way that reduces coverage, or major risk assumption.

For a material deviation:

```text
STOP implementation
 ↓
Lead sets STATUS.md → PLAN_REWORK
 ↓
Implementation creates next PLAN version
 ↓
Lead PLAN_REVIEW
 ↓
APPROVED
 ↓
continue implementation
```

Do not finish an alternative design first and explain it later.

## Stable Review Target

Every implementation round submitted for Review must produce:

```text
Review Target
Branch: <branch or detached>
Base SHA: <sha>
Head SHA: <sha>
Working Tree: CLEAN
Frozen: true
```

Rules:

1. `Head SHA` is authoritative.
2. Implementation must commit intended review changes and make the working tree clean.
3. `IMPL-NNN.md` binds to Base SHA and Head SHA.
4. After READY_FOR_REVIEW, Implementation must not mutate that Review Target.
5. Any post-submission code change creates a new implementation round and new Head SHA.
6. Review verifies checked-out HEAD equals declared Head SHA before substantive review.
7. Review compares Base SHA → Head SHA.
8. On mismatch, stop Review and report `REVIEW_TARGET_MISMATCH`.

A branch name is descriptive only because it may move.

## Independent Review context

Review should begin with a fresh execution context whenever the runtime permits.

Review MUST NOT rely on:
- Implementation private reasoning;
- implementation conversation history;
- self-review conclusions as proof.

Review MAY consume:
- TASK.md;
- approved PLAN version;
- IMPL-NNN.md;
- repository state at exact Head SHA;
- Base→Head diff;
- test evidence;
- prior REVIEW artifacts for re-review.

Principle: **share artifacts, not private reasoning**.

## Review and rework

Review result is PASS or FAIL. `REVIEW_TARGET_MISMATCH` is a protocol failure that stops substantive review.

When Review fails:

1. Lead validates findings.
2. Confirmed findings become `RW-xxx` entries in TASK.md.
3. Lead sets STATUS.md → REWORK.
4. Implementation creates a new implementation round and Head SHA.
5. Review creates a new REVIEW-NNN.md.

A re-review checks prior blockers, the new diff, original requirements/ACs, and new regression risk.

## Final acceptance

After PASS, Lead creates `ACCEPTANCE.md` bound to:

- accepted Plan version;
- accepted Implementation round;
- accepted Review round;
- accepted Head SHA;
- REQ / AC verification;
- test evidence;
- residual risks.

Only after ACCEPTANCE.md exists may Lead set STATUS.md → ACCEPTED.

## Handoff contract

Every handoff identifies:

- Task ID;
- task directory;
- current lifecycle state;
- requested action;
- expected output artifact;
- exact Plan/Implementation/Review version when relevant;
- exact Head SHA for Review.

## Workflow selection

Use:
- `workflows/standard.md`
- `workflows/complex.md`
- `workflows/bugfix.md`

## Runtime and terminal adapters

Use:
- `adapters/warp.md`
- `runtimes/codex.md`
- `runtimes/pi.md`
- `runtimes/generic.md`

Adapters may describe startup, tools, worktrees, subagents, RPC, Code Mode, or sandboxing, but may not bypass protocol gates.
