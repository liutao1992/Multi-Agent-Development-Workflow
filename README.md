# Multi-Agent Development Workflow

A runtime-independent multi-agent software development skill built around a simple principle:

> Separate **what should be built**, **how it should be built**, and **whether it was built correctly**.

The default workflow uses three roles:

- **Lead Agent** — requirements, task definition, plan approval, rework decisions, final acceptance
- **Implementation Agent** — investigation, planning, implementation, testing, implementation report
- **Review Agent** — independent verification, regression review, testing, PASS / FAIL

The workflow is designed to work with Codex, Pi, Claude Code, Cursor, OpenCode, or other coding agents.

Warp is the preferred interactive terminal environment, using a three-pane layout:

```text
┌──────────────────────────┬──────────────────────────┐
│ Lead Agent               │ Implementation Agent     │
│                          │                          │
│ Task / Plan Approval     │ Plan / Code / Test       │
│ Rework / Acceptance      │                          │
│                          ├──────────────────────────┤
│                          │ Review Agent             │
│                          │                          │
│                          │ Verify / PASS / FAIL     │
└──────────────────────────┴──────────────────────────┘
```

## Repository structure

```text
.
├── SKILL.md
├── roles/
│   ├── lead.md
│   ├── implementation.md
│   └── review.md
├── workflows/
│   ├── standard.md
│   ├── complex.md
│   └── bugfix.md
├── templates/
│   ├── INDEX.md
│   ├── TASK.md
│   ├── PLAN.md
│   ├── IMPLEMENTATION.md
│   ├── REVIEW.md
│   └── STATUS.md
├── adapters/
│   └── warp.md
└── runtimes/
    ├── pi.md
    ├── codex.md
    └── generic.md
```

## Task coordination

Each development task has its own namespace:

```text
.agent-team/
├── INDEX.md
└── tasks/
    └── TASK-YYYYMMDD-NNN-short-name/
        ├── TASK.md
        ├── PLAN.md
        ├── IMPLEMENTATION.md
        ├── REVIEW.md
        └── STATUS.md
```

Example:

```text
TASK-20261003-001-word-review-redesign
```

The workflow maintains traceability across:

```text
Requirement
  ↓
Acceptance Criterion
  ↓
Plan Step
  ↓
Implementation Change
  ↓
Test
  ↓
Review Evidence
```

## Core lifecycle

```text
User
 ↓
Lead
 ↓
TASK.md
 ↓
Implementation Agent
 ↓
PLAN.md
 ↓
Lead Plan Approval
 ↓
Implementation
 ↓
IMPLEMENTATION.md
 ↓
Review
 ↓
REVIEW.md
 ↓
Lead
 ├─ REWORK → Implementation
 └─ ACCEPTED
```

See [SKILL.md](./SKILL.md) for the full protocol.
