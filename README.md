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

### Concurrency rule

A single Git working tree is one mutable Code Plane. Do not run two automated Tasks against the same working tree at the same time.

```text
one working tree
→ one automated Task at a time
```

The standalone Process/Queue runtime enforces this with a Code Plane lock. The lock is fail-closed: a stale lock is not automatically stolen because an orphan worker may still be changing the Code Plane. For true parallel Tasks, create a separate Git worktree per Task. Native SubAgent mode must follow the same rule even though its scheduling happens inside the parent Agent.

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

Native SubAgent orchestration is **Skill-level orchestration**: Lead uses the host runtime's native child-agent tools. The bundled `agent-team` CLI implements only Process and Queue fallback transports.

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

Process mode also enforces runtime safety:

- one automated Task per working tree through a Code Plane lock;
- clean Code Plane before every dispatch;
- real per-worker timeout for Codex and Pi;
- process-group termination on timeout/cancel;
- executable lifecycle transition validation after every Lead action;
- evidence gates for Plan approval, Review PASS/FAIL, Review Target, BLOCKED resume, and final ACCEPTED;
- role postconditions after every worker;
- whole-project Control Plane write-boundary validation (runtime metadata excluded);
- immutable existing Plan / IMPL / REVIEW artifacts;
- Review cannot change HEAD/index/worktree or STATUS;
- Planning Impl cannot change Code Plane or STATUS;
- Implementation Impl must leave a clean committed Code Plane and create exactly one IMPL artifact;
- Lead cannot modify Code Plane.

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

Queue jobs are project-scoped. When multiple projects share an external `AGENT_TEAM_DIR`, each project gets a fingerprint namespace. Workers reject jobs whose project root/fingerprint does not match.

Queue jobs use lease + cancellation semantics:

```text
QUEUED
  ↓
CLAIMED / RUNNING + lease
  ↓
SUCCEEDED / FAILED / CANCELLED
                    └─ or QUARANTINED when orphan safety is uncertain
```

Expired claims are requeued only when the previous child process identity is known and confirmed unable to execute.

For a live stale PID, the runtime also verifies recorded process identity (PID + process group/start-time/command where available) before terminating anything. A live PID that cannot be proven to be the original child is never killed; the claim is quarantined as `UNKNOWN_PROCESS_IDENTITY`.

If an expired/malformed claim has no trustworthy `child_pid`, or a child cannot be confirmed quiesced, the claim moves to `quarantined/` as `UNKNOWN_ORPHAN_RISK`. New automatic runs/workers fail closed until the quarantine is inspected.

A timed-out orchestrator cancels the job and attempts to quiesce any claimed child process before returning; a running worker also observes cancellation and terminates its child runtime instead of continuing to make ghost changes.

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

If `AGENT_TEAM_DIR` is external and shared by multiple projects, storage becomes project-scoped:

```text
<AGENT_TEAM_DIR>/
└── projects/
    └── <project-fingerprint>/
        ├── tasks/
        └── runtime/
```

If a custom Control Root is still inside the Git working tree, the CLI verifies that it is untracked and adds that path to `.git/info/exclude`. A tracked Control Root is rejected.

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
"$AGENT_TEAM" doctor
```

`doctor` does not require Codex/Pi to be installed. It reports missing runtimes instead of failing and does not create Control Plane directories.

Current Task state:

```bash
"$AGENT_TEAM" status TASK-20261003-001-ios-system-dictionary-meaning
```

`status` is read-only: it does not resolve a runtime, create directories, or modify `.git/info/exclude`.

Resume a BLOCKED Task after a human decision:

```bash
"$AGENT_TEAM" \
  --runtime codex \
  resume TASK-20261003-001-ios-system-dictionary-meaning \
  "Use a backward-compatible migration"
```

`run` intentionally stops at `BLOCKED`. Only `resume` asks Lead to consume the human resolution, transition exactly to the recorded Resume State, validate that transition, and then continue automation.

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

### Requirement Contract is snapshot-bound

`TASK.md` is the requirement source of truth, and its executable contract is versioned.

The contract hash covers:

```text
Objective
Requirements
Acceptance Criteria
Constraints
Dependencies
Out of Scope
```

TASK records:

```text
Task Contract Revision: N
Task Contract Hash: <SHA-256>
```

The active PLAN, IMPL, REVIEW, STATUS and ACCEPTANCE evidence must bind the same revision/hash.

When Lead changes contract content:

```text
Revision N
   ↓ amendment
Revision N+1
   ↓
Requirement Change Log records:
- Revision
- Previous Hash
- New Hash
   ↓
existing Plan / IMPL / REVIEW evidence becomes stale
   ↓
PLAN_REWORK
```

A changed Task Contract therefore cannot silently reuse an old Plan, Review or Acceptance path.

`Rework Requirements` contains Review remediation instructions and is excluded from the requirement hash. Lead may update only that TASK section during `REVIEWING -> REWORK`, with valid FAIL or MISMATCH evidence. Contract revision/hash and all other TASK content remain unchanged. Product requirement changes still require a contract amendment and `PLAN_REWORK`.

Tasks created with the earlier hash definition (which included Rework Requirements) require regenerated contract bindings and evidence; existing immutable artifacts must not be edited to substitute the new hash.

### Plan ownership is mechanically enforced

Plan content and Plan approval have different owners:

```text
Impl
  owns every section except ## Approval

Lead
  may change only ## Approval
```

The runtime hashes each Plan after removing the `## Approval` block. Existing Plan content hashes must not change.

Approval is a one-time decision. Only the current PENDING Plan may change during `PLAN_REVIEW`:

```text
PENDING → APPROVED
or
PENDING → REWORK
```

After that decision, the entire Plan version—including the Approval block—is frozen. Older approval history cannot be rewritten.

When a Plan enters `PLAN_REVIEW`, both STATUS and the Plan file must say:

```text
PENDING
```

so Impl cannot self-approve a Plan.

## 10. Executable lifecycle enforcement

The Markdown Transition Table is also enforced by Python.

After every Lead action the runtime validates:

```text
before state
+
after state
+
required evidence
+
allowed transition
```

Examples:

```text
CREATED → ACCEPTED
= rejected

PLAN_REVIEW → READY_FOR_IMPLEMENTATION
= requires APPROVED in STATUS + Plan artifact

IMPLEMENTING → READY_FOR_REVIEW
= requires frozen IMPL target + exact full 40-char Code Head SHA

REVIEWING → READY_FOR_FINAL_ACCEPTANCE
= requires REVIEW Result PASS

READY_FOR_FINAL_ACCEPTANCE → ACCEPTED
= requires ACCEPTANCE.md + current PASS Review
+ matching accepted Code Head
+ current real Git HEAD still equals the reviewed Code Head

<any> → BLOCKED
= requires Resume State = previous lifecycle state
```

This turns the Transition Table from prompt guidance into an executable protocol.

Review evidence is machine-validated for all three exits.

For PASS or FAIL, the Review must bind:

```text
Reviewed Implementation
=
STATUS Current Implementation

Declared Code Head
=
Observed Review Head
=
STATUS Code Head
=
current Git HEAD

Protocol Status = READY_FOR_REVIEW

Unstaged Diff Clean = YES
Staged Diff Clean = YES
Status Porcelain Clean = YES
Control Plane Excluded = YES
```

For FAIL, STATUS and REVIEW must both say `FAIL`, the same implementation/head checks apply, and at least one blocking `REV-NNN` issue must exist.

For target mismatch:

```text
Protocol Status = REVIEW_TARGET_MISMATCH
Review Result = N/A
Declared Code Head = submitted STATUS Code Head
Observed Code Head = current Git HEAD
```

Final Acceptance repeats both the reviewed Code Head check and Task Contract check to close Code and Requirement TOCTOU gaps.

## 11. When automation stops

Automatic execution stops rather than guessing when:

- `STATUS = BLOCKED`;
- a genuine product or requirement decision needs a human;
- a worker/runtime fails;
- no protocol progress is produced;
- the Review target is invalid;
- a required worker disappears;
- a worker violates its role postconditions;
- the Code Plane is dirty before dispatch;
- another automated Task already owns the same working tree;
- the maximum orchestration step limit is reached.

Example:

```text
Need human decision:
Should this database migration be destructive or backward-compatible?
```

At that point Lead should ask the user.

After the decision:

- Native SubAgent / interactive Lead: provide the decision to Lead and continue;
- standalone Process/Queue mode: use the explicit `resume` command.

```bash
"$AGENT_TEAM" --runtime codex resume TASK-... "human decision"
```

The decision must be persisted in STATUS → Blocked Resolution before the workflow resumes.

---

## 12. Lifecycle overview

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

## 13. Documentation

- [Skill protocol](./skills/multi-agent-development-workflow/SKILL.md)
- [Native SubAgent orchestration](./skills/multi-agent-development-workflow/automation/subagent.md)
- [Standalone Orchestrator fallback](./skills/multi-agent-development-workflow/automation/orchestrator.md)
- [Warp adapter](./skills/multi-agent-development-workflow/adapters/warp.md)
- [Codex runtime](./skills/multi-agent-development-workflow/runtimes/codex.md)
- [Pi runtime](./skills/multi-agent-development-workflow/runtimes/pi.md)
