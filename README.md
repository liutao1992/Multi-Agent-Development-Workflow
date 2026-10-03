# Multi-Agent Development Workflow

A runtime-independent software-development workflow built around three roles:

- **Lead** — requirement definition, lifecycle control, Plan approval, rework decisions, final acceptance
- **Impl** — investigation, Plan creation, implementation, tests, implementation evidence
- **Review** — fresh-context independent verification of an exact Code Plane snapshot

Only **Lead** may transition lifecycle state and declare a task `ACCEPTED`.

> The `feature/agent-orchestrator` branch adds experimental automatic orchestration.  
> `main` remains the stable manual-handoff version.

---

## 1. Which mode should I use?

| Mode | Recommended for | Human handoff | Warp panes |
|---|---|---:|---:|
| **Native SubAgent** | Normal interactive development | No | 1 is enough |
| **Process fallback** | CI / unattended local execution | No | Not required |
| **Queue fallback** | Watching Impl and Review in separate Warp panes | No | 3 |
| Manual | Runtime without automation support | Yes | Any |

Recommended order:

```text
native-subagent
      ↓ unavailable
process
      ↓ need visible Warp workers
queue
      ↓ automation unavailable
manual
```

For normal use, **start with Native SubAgent mode**.

---

## 2. Install the Skill

The installable Skill directory is:

```text
skills/multi-agent-development-workflow/
├── SKILL.md
├── roles/
├── workflows/
├── templates/
├── adapters/
├── runtimes/
├── automation/
└── scripts/
```

### Codex — manual install

For the automatic-orchestration branch:

```bash
git clone -b feature/agent-orchestrator \
  https://github.com/liutao1992/Multi-Agent-Development-Workflow.git

mkdir -p ~/.codex/skills

cp -R \
  Multi-Agent-Development-Workflow/skills/multi-agent-development-workflow \
  ~/.codex/skills/multi-agent-development-workflow
```

Installed layout:

```text
~/.codex/skills/
└── multi-agent-development-workflow/
    ├── SKILL.md
    ├── roles/
    ├── workflows/
    ├── templates/
    ├── adapters/
    ├── runtimes/
    ├── automation/
    └── scripts/
```

If your Skill installer can install a repository subdirectory directly, install:

```text
skills/multi-agent-development-workflow/
```

---

## 3. Recommended usage: Native SubAgent

### What this mode does

Native mode uses the runtime's real parent/child Agent capability:

```text
You
 ↓
Lead = Parent / Root Agent
 ├── Impl SubAgent       ← reused within the same Task
 └── Review SubAgent     ← NEW for every Review round
```

Lead automatically drives:

```text
Task
 ↓
Impl creates Plan
 ↓
Lead approves Plan
 ↓
same Impl implements + tests
 ↓
Lead freezes Review target
 ↓
fresh Review SubAgent
 ├── FAIL → Lead → same Impl rework → fresh Review
 └── PASS → Lead final acceptance
 ↓
ACCEPTED
```

You do **not** need to manually type `继续` into Impl or `Review` into Review.

### Start a new Task

Open the target project in your coding Agent and talk only to **Lead**:

```text
Use multi-agent-development-workflow.
Role: Lead.
Mode: Automatic.
Transport: native-subagent.

新建任务：
增加 iOS 系统词典释义功能。
```

After that, Lead should automatically:

1. create `.agent-team/tasks/<TASK-ID>/`;
2. create `TASK.md` and `STATUS.md`;
3. spawn/reuse Impl for Plan and implementation;
4. perform Plan Gate itself;
5. spawn a fresh Review SubAgent for each Review round;
6. drive rework automatically when Review fails;
7. create `ACCEPTANCE.md` and finish at `ACCEPTED`.

### Continue an existing Task

```text
Use multi-agent-development-workflow.
Role: Lead.
Mode: Automatic.
Transport: native-subagent.

继续 TASK-20261003-001-ios-system-dictionary-meaning
```

Lead reads `STATUS.md` and resumes from the current lifecycle state.

### Short form after Lead is already bound

If the current Lead session already knows the Skill and the Task:

```text
继续
```

That is enough.

### Impl reuse rule

For one Task:

```text
Impl-1
  ├── Plan
  ├── Implementation
  └── Rework
```

Lead should reuse the same Impl child when possible so implementation context is preserved.

### Review freshness rule

Every Review round gets a new child:

```text
IMPL-001 → Review-1 → REVIEW-001
IMPL-002 → Review-2 → REVIEW-002
IMPL-003 → Review-3 → REVIEW-003
```

A Review SubAgent must not inherit Impl private reasoning.

> A separate `codex exec` process or Pi RPC process is a **worker process**, not a native SubAgent.

---

## 4. Do I still need three Warp panes?

### Native SubAgent mode

No.

One Lead pane is enough:

```text
┌──────────────────────────────────────┐
│ Lead / Parent Agent                  │
│                                      │
│ automatically spawns Impl / Review   │
│ automatically drives STATUS          │
│ automatically handles rework         │
│ automatically accepts the Task       │
└──────────────────────────────────────┘
```

You can keep extra panes for logs or Git inspection, but they are not required for orchestration.

### If you want visible Impl / Review panes

Use **Queue fallback** instead. See section 6.

---

## 5. Process fallback

Use this when the current runtime does not expose native SubAgent collaboration.

The bundled CLI launches separate Codex/Pi worker processes and drives the same lifecycle automatically.

Define the CLI path after installing the Skill:

```bash
AGENT_TEAM="$HOME/.codex/skills/multi-agent-development-workflow/scripts/agent-team"
```

### Check the environment

```bash
"$AGENT_TEAM" --runtime codex doctor
```

### Start from a requirement

```bash
"$AGENT_TEAM" \
  --runtime codex \
  --transport process \
  start "增加 iOS 系统词典释义功能"
```

### Continue an existing Task

```bash
"$AGENT_TEAM" \
  --runtime codex \
  --transport process \
  run TASK-20261003-001-ios-system-dictionary-meaning
```

### Pi

```bash
"$AGENT_TEAM" \
  --runtime pi \
  --transport process \
  run TASK-20261003-001-ios-system-dictionary-meaning
```

Process mode still preserves:

- Lead-only lifecycle transitions;
- Plan Gate;
- immutable Plan / IMPL / REVIEW artifacts;
- stable Git Review target;
- fresh Review context;
- automatic rework loop.

---

## 6. Warp three-pane Queue fallback

Use this mode when you want to **see Impl and Review running in dedicated Warp panes**.

Layout:

```text
┌──────────────────────────────┬──────────────────────────────┐
│ Lead / Orchestrator          │ Impl Worker                  │
│                              │                              │
│ controls STATUS              │ consumes Impl jobs           │
│ dispatches automatically     ├──────────────────────────────┤
│ final acceptance             │ Review Worker                │
│                              │ consumes Review jobs         │
└──────────────────────────────┴──────────────────────────────┘
```

Do not enable Warp synchronized input.

Set:

```bash
AGENT_TEAM="$HOME/.codex/skills/multi-agent-development-workflow/scripts/agent-team"
```

### Right-top pane — Impl

Run once:

```bash
"$AGENT_TEAM" --runtime codex worker Impl
```

Leave this process running.

### Right-bottom pane — Review

Run once:

```bash
"$AGENT_TEAM" --runtime codex worker Review
```

Leave this process running.

### Left pane — Lead / Orchestrator

Start a new Task:

```bash
"$AGENT_TEAM" \
  --runtime codex \
  --transport queue \
  start "增加 iOS 系统词典释义功能"
```

Or continue an existing Task:

```bash
"$AGENT_TEAM" \
  --runtime codex \
  --transport queue \
  run TASK-20261003-001-ios-system-dictionary-meaning
```

After that, no manual pane switching is required.

The Orchestrator automatically performs:

```text
Lead
 ↓
queue → Impl pane
 ↓
Lead
 ↓
queue → Impl pane
 ↓
Lead
 ↓
queue → Review pane
 ↓
Lead
 ├── rework loop
 └── acceptance
```

### Important

Queue mode does **not** inject prompts into arbitrary interactive Codex/Pi sessions already open in those panes.

The right-side panes must run:

```text
agent-team worker Impl
agent-team worker Review
```

Those worker processes launch the configured runtime when a job arrives.

---

## 7. Where task data is stored

By default, Agent Team data lives inside the target project:

```text
<project-root>/
├── .agent-team/
│   ├── INDEX.md
│   ├── runtime/
│   └── tasks/
│       └── TASK-YYYYMMDD-NNN-short-name/
│           ├── TASK.md
│           ├── STATUS.md
│           ├── plans/
│           ├── implementations/
│           ├── reviews/
│           └── ACCEPTANCE.md
└── project source...
```

The Skill must not automatically use:

```text
/private/tmp/...
/tmp/...
~/.agent-team/...
```

unless you explicitly configure an external Control Root.

The default root is resolved from:

```bash
git rev-parse --show-toplevel
```

and becomes:

```text
<project-root>/.agent-team/
```

### Git rule

`.agent-team/` is Control Plane data and must not enter the Code Plane commit history.

The Skill normally adds it to:

```text
.git/info/exclude
```

Verify:

```bash
git ls-files .agent-team
git check-ignore -q .agent-team/
```

`git ls-files .agent-team` should return nothing.

---

## 8. Role files and task lookup

Role definitions:

```text
Lead   → roles/lead.md
Impl   → roles/impl.md
Review → roles/review.md
```

For a Task:

```text
<project-root>/.agent-team/tasks/<TASK-ID>/
```

Every role reads:

```text
STATUS.md
```

first.

Then it follows the exact artifact references recorded there.

### Lead

Reads:

```text
STATUS.md
TASK.md
plans/PLAN-vNNN.md
implementations/IMPL-NNN.md
reviews/REVIEW-NNN.md
ACCEPTANCE.md
```

### Impl

Reads:

```text
STATUS.md
TASK.md
approved Plan
failed Review / confirmed RW items when reworking
```

### Review

Reads:

```text
STATUS.md
TASK.md
approved Plan or fast-path marker
exact IMPL-NNN
exact Code Head SHA
Git diffs
test evidence
```

Agents must not guess an artifact merely because it has the highest filename number.

---

## 9. Useful commands

Using:

```bash
AGENT_TEAM="$HOME/.codex/skills/multi-agent-development-workflow/scripts/agent-team"
```

Environment check:

```bash
"$AGENT_TEAM" --runtime codex doctor
```

Current Task state:

```bash
"$AGENT_TEAM" status TASK-20261003-001-ios-system-dictionary-meaning
```

Automatic process fallback:

```bash
"$AGENT_TEAM" --runtime codex --transport process run TASK-...
```

Warp queue fallback:

```bash
"$AGENT_TEAM" --runtime codex --transport queue run TASK-...
```

The standalone CLI intentionally rejects:

```bash
"$AGENT_TEAM" --transport subagent ...
```

because native SubAgents belong to the already-running Lead parent session. The CLI must not pretend that a child OS process is a native SubAgent.

---

## 10. When automation stops

Automatic execution stops rather than guessing when:

- `STATUS = BLOCKED`;
- a genuine product or requirement decision needs a human;
- a worker/runtime fails;
- no protocol progress is produced;
- the Review target is invalid;
- a required worker disappears;
- the maximum orchestration step limit is reached.

Example:

```text
Need human decision:
Should this database migration be destructive or backward-compatible?
```

At that point Lead should ask the user.

After the decision:

```text
继续 TASK-...
```

resumes the workflow.

---

## 11. Lifecycle overview

```text
User requirement
      ↓
Lead
      ↓
Impl → PLAN
      ↓
Lead Plan Gate
      ↓
Impl → Code + Tests + IMPL
      ↓
Lead freezes Review target
      ↓
fresh Review
   ┌───────┴────────┐
   │                │
 FAIL              PASS
   │                │
 Lead → Rework      Lead
   │                │
 Impl               ACCEPTANCE.md
   │                │
 fresh Review       ACCEPTED
   └──── loop
```

Lifecycle source of truth:

```text
STATUS.md
```

Requirement source of truth:

```text
TASK.md
```

Implementation source of truth:

```text
Code Head SHA
```

Verification evidence:

```text
REVIEW-NNN.md
```

---

## 12. Documentation

- [Skill protocol](./skills/multi-agent-development-workflow/SKILL.md)
- [Native SubAgent orchestration](./skills/multi-agent-development-workflow/automation/subagent.md)
- [Standalone Orchestrator fallback](./skills/multi-agent-development-workflow/automation/orchestrator.md)
- [Warp adapter](./skills/multi-agent-development-workflow/adapters/warp.md)
- [Codex runtime](./skills/multi-agent-development-workflow/runtimes/codex.md)
- [Pi runtime](./skills/multi-agent-development-workflow/runtimes/pi.md)
