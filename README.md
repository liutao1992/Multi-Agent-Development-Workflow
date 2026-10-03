# Multi-Agent Development Workflow

A runtime-independent, artifact-driven development protocol for coordinating the three roles:

- **Lead** — task definition, lifecycle control, plan approval, rework decisions, final acceptance
- **Impl** — investigation, planning, implementation, testing, immutable implementation evidence
- **Review** — fresh-context independent verification of an exact Code Plane snapshot

Only **Lead** can declare a task `ACCEPTED`.

## Installable Skill

The repository root is the package repository. The actual installable Skill lives at:

```text
skills/multi-agent-development-workflow/
├── SKILL.md
├── roles/
├── workflows/
├── templates/
├── adapters/
└── runtimes/
```

This layout lets installers treat `skills/multi-agent-development-workflow/` as a complete Skill directory instead of trying to install a root-level `SKILL.md` file.

## Repository structure

```text
Multi-Agent-Development-Workflow/
├── README.md
└── skills/
    └── multi-agent-development-workflow/
        ├── SKILL.md
        ├── roles/
        │   ├── lead.md
        │   ├── impl.md
        │   └── review.md
        ├── workflows/
        │   ├── standard.md
        │   ├── complex.md
        │   └── bugfix.md
        ├── templates/
        ├── adapters/
        │   └── warp.md
        └── runtimes/
            ├── codex.md
            ├── pi.md
            └── generic.md
```

## Manual Codex install

If your installer does not support selecting the Skill subdirectory automatically, clone the repository and copy/link the Skill directory:

```bash
git clone https://github.com/liutao1992/Multi-Agent-Development-Workflow.git
mkdir -p ~/.codex/skills
cp -R Multi-Agent-Development-Workflow/skills/multi-agent-development-workflow \
  ~/.codex/skills/multi-agent-development-workflow
```

The installed result should be:

```text
~/.codex/skills/
└── multi-agent-development-workflow/
    ├── SKILL.md
    ├── roles/
    ├── workflows/
    ├── templates/
    ├── adapters/
    └── runtimes/
```

## Warp quick use

Bind each pane once:

```text
Lead pane:
Use multi-agent-development-workflow. Role: Lead.

Impl pane:
Use multi-agent-development-workflow. Role: Impl.

Review pane:
Use multi-agent-development-workflow. Role: Review.
```

Then normal use can stay short:

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

See [the Skill definition](./skills/multi-agent-development-workflow/SKILL.md) for the full protocol.


## Project-local Agent Team data

For normal use, task coordination data is stored in the current project's Git root:

```text
<project-root>/
├── .agent-team/
│   ├── INDEX.md
│   └── tasks/
└── ...
```

The Skill should **not** automatically put task data in `/private/tmp` or `/tmp`.

Initialize it with:

```bash
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
mkdir -p "$PROJECT_ROOT/.agent-team/tasks"
grep -qxF ".agent-team/" "$PROJECT_ROOT/.git/info/exclude" 2>/dev/null \
  || printf "\n.agent-team/\n" >> "$PROJECT_ROOT/.git/info/exclude"
```

An external Control Root is only used when explicitly configured.


## Role entry and task lookup

Each role has a fixed entry file inside the installed Skill:

```text
Lead   → roles/lead.md
Impl   → roles/impl.md
Review → roles/review.md
```

For task `<TASK-ID>`, task artifacts are located under:

```text
<project-root>/.agent-team/tasks/<TASK-ID>/
```

Every role reads `STATUS.md` first and follows the artifact references recorded there. The user should not need to manually paste Plan or Review content between Warp panes.
