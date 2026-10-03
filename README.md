# Multi-Agent Development Workflow

A runtime-independent development protocol for coordinating **Lead**, **Implementation**, and **Review** agents across Codex, Pi, Claude Code, Cursor, OpenCode, or other coding agents.

The protocol separates three questions:

- **What should be built?** → Lead Agent
- **How should it be built?** → Implementation Agent
- **Was it built correctly?** → Review Agent

Only the Lead Agent can declare a task **ACCEPTED**.

Warp is the preferred interactive terminal environment, but the protocol is terminal- and runtime-independent.

## Core lifecycle

```text
User
 ↓
Lead → TASK.md
 ↓
Implementation → PLAN-v001.md
 ↓
Lead Plan Gate
 ├─ PLAN_REWORK → PLAN-v002.md
 └─ APPROVED
       ↓
Implementation → Git snapshot → IMPL-001.md
 ↓
Independent Review → REVIEW-001.md
 ├─ FAIL → Lead → RW-001 → IMPL-002.md → REVIEW-002.md
 └─ PASS
       ↓
Lead Final Acceptance
 ↓
ACCEPTANCE.md
 ↓
ACCEPTED
```

## Task workspace

Each task has its own namespace and immutable round history:

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

## Sources of truth

| Concern | Source of truth |
|---|---|
| Requirements | `TASK.md` |
| Approved implementation intent | approved `PLAN-vNNN.md` |
| Implemented code | immutable Git Head SHA |
| Verification evidence | `REVIEW-NNN.md` |
| Current lifecycle state | `STATUS.md` |
| Final closure | `ACCEPTANCE.md` |
| Multi-task dashboard | `INDEX.md` (derived only) |

## Stable review target

Every implementation round submitted for review must bind to a stable Git snapshot:

```text
Branch: feature/foo
Base SHA: abc123
Head SHA: def456
Working Tree: CLEAN
Frozen: true
```

The **Head SHA** is the authoritative review target. Any later code change creates a new implementation round and review round.

## Warp layout

```text
┌──────────────────────────┬──────────────────────────┐
│ Lead Agent               │ Implementation Agent     │
│                          │                          │
│ Task / Plan Gate         │ Plan / Code / Test       │
│ Rework / Acceptance      │                          │
│                          ├──────────────────────────┤
│                          │ Review Agent             │
│                          │                          │
│                          │ Verify / PASS / FAIL     │
└──────────────────────────┴──────────────────────────┘
```

See [SKILL.md](./SKILL.md) for the executable protocol.
