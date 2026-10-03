# Warp Adapter

Warp is the preferred human-visible control surface. It does not define lifecycle semantics.

## Default layout

```text
┌──────────────────────────────┬──────────────────────────────┐
│ Lead                   │ Impl         │
│ STATUS / Task / Plan Gate    │ Plan / Code / Test           │
│ Rework / Acceptance          │ Code Snapshot / IMPL         │
│                              ├──────────────────────────────┤
│                              │ Review                 │
│                              │ Fresh Review / Exact SHA     │
└──────────────────────────────┴──────────────────────────────┘
```

Do not enable synchronized input.

## One-time pane binding

When opening a new Warp tab/session, bind each pane once:

```text
Lead pane:
Use multi-agent-development-workflow. Role: Lead.

Impl pane:
Use multi-agent-development-workflow. Role: Impl.

Review pane:
Use multi-agent-development-workflow. Role: Review.
```

After binding, do not paste the full protocol at every handoff.

## Daily short commands

Typical usage:

```text
Lead:
新建任务：<requirement>

Impl:
继续 <TASK-ID>

Lead:
继续 <TASK-ID>

Impl:
继续 <TASK-ID>

Review:
Review <TASK-ID>

Lead:
继续 <TASK-ID>
```

If the session already has one unambiguous Task bound, the Task ID may be omitted:

```text
继续
Review
验收
```

Each pane must recover authoritative state from STATUS.md and the task artifacts. Short commands never weaken role boundaries or lifecycle gates.

## Control Plane location

### Shared single working tree

You may keep `.agent-team/` inside the project directory only when it is excluded from Code Plane Git tracking.

Prefer a local exclude so the project does not need a workflow-specific committed `.gitignore` entry:

```bash
printf "\n.agent-team/\n" >> .git/info/exclude
```

Verify:

```bash
git ls-files .agent-team
git check-ignore -q .agent-team/
```

Do not force-add it.

### Multiple worktrees / concurrent agents

Use one shared Control Plane directory outside all code worktrees, for example:

```text
workspace/
├── project-main/
├── project-implementation/
├── project-review/
└── project.agent-team/
```

All three agents reference the same external Control Root.

## Stable Review handoff

Before Review, Impl commits Code Plane changes and records:

- Task Baseline SHA;
- Previous Head SHA;
- Code Head SHA.

Review verifies:

```bash
git rev-parse HEAD
git diff --quiet
git diff --cached --quiet
git status --porcelain
```

Only an exact clean Code Plane target may be reviewed.

Any Code Plane change after submission creates a new implementation round.
