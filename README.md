# Multi-Agent Development Workflow

A runtime-independent, artifact-driven development protocol for coordinating **Lead**, **Implementation**, and **Review** agents across Codex, Pi, Claude Code, Cursor, OpenCode, or other coding agents.

The protocol separates:

- **What should be built?** → Lead Agent
- **How should it be built?** → Implementation Agent
- **Was it built correctly?** → Review Agent

Only the Lead Agent can declare a task **ACCEPTED**.

Warp is the preferred interactive terminal environment, but terminal and agent runtime are adapters rather than protocol authorities.

## Quick use in Warp

Bind each pane once per session:

```text
Left:       Use multi-agent-development-workflow. Role: Lead.
Right top:  Use multi-agent-development-workflow. Role: Implementation.
Right bottom: Use multi-agent-development-workflow. Role: Review.
```

After that, normal interaction can stay short:

```text
Lead:
新建任务：增加聊天记录持久化

Implementation:
继续 TASK-20261003-001-chat-history-persistence

Lead:
继续 TASK-20261003-001-chat-history-persistence

Implementation:
继续 TASK-20261003-001-chat-history-persistence

Review:
Review TASK-20261003-001-chat-history-persistence

Lead:
继续 TASK-20261003-001-chat-history-persistence
```

When a pane already has an unambiguous Task bound, even `继续`, `Review`, or `验收` is enough. The Agent must recover lifecycle state and current artifacts from the Control Plane instead of asking the user to repeat them.

## Core lifecycle

```text
User
 ↓
Lead → TASK.md + STATUS.md
 ↓
Implementation → PLAN-v001.md
 ↓
Lead Plan Gate
 ├─ REWORK → PLAN-v002.md
 └─ APPROVED
       ↓
Implementation → Code Plane commit → IMPL-001.md
 ↓
Independent Review → exact Code Head SHA → REVIEW-001.md
 ├─ FAIL → RW-001 → IMPL-002.md → REVIEW-002.md
 └─ PASS
       ↓
Lead → ACCEPTANCE.md
 ↓
ACCEPTED
```

## Control Plane vs Code Plane

The protocol explicitly separates workflow metadata from reviewed code:

```text
Control Plane
.agent-team/
TASK / STATUS / PLAN / IMPL / REVIEW / ACCEPTANCE

Code Plane
production source / tests / migrations / resources / configuration
```

**Control Plane artifacts MUST NOT be tracked in the reviewed Code Plane Git history.**

Recommended local setup:

- shared single worktree: keep `.agent-team/` inside the project directory but exclude it with `.git/info/exclude`;
- multiple worktrees / concurrent agents: use one shared control directory outside all code worktrees.

This avoids the self-referential problem where an IMPL artifact records a Git SHA and committing that artifact changes the SHA.

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

## Review snapshots

Every task freezes a **Task Baseline SHA** at creation.

Each implementation round records:

```text
Task Baseline SHA
Previous Head SHA
Code Head SHA
```

Review uses both:

- Task Baseline SHA → Code Head SHA: full task impact;
- Previous Head SHA → Code Head SHA: current implementation/rework round.

The reviewer also verifies the Code Plane working tree is clean before substantive review.

See [SKILL.md](./SKILL.md) for the full executable protocol.
