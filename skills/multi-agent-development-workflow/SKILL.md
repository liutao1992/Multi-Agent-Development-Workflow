---
name: multi-agent-development-workflow
description: Use for non-trivial software-development tasks that need multi-agent coordination, task definition, plan approval, implementation, independent review, rework, stable Git code snapshots, lifecycle control, and final acceptance across Codex, Pi, Warp, or other coding-agent environments.
---

# Multi-Agent Development Workflow

## Purpose

This skill defines a deterministic, runtime-independent development protocol using three logical roles:

1. **Lead** — requirements, lifecycle control, plan approval, rework decisions, final acceptance.
2. **Impl** — investigation, planning, implementation, testing, immutable implementation-round evidence.
3. **Review** — fresh-context independent verification of an exact Code Plane Git snapshot.

Only Lead may declare a task **ACCEPTED**.

## Invocation protocol

### Existing task

When an existing Task ID is known or discovered:

1. Determine acting role: Lead, Impl, or Review. If orchestration is requested without an explicit role, use Lead.
2. Determine exact Task ID and Control Plane task directory.
   - Prefer an explicit Task ID.
   - If exactly one active task exists, it may be selected from INDEX.md.
   - If multiple active tasks exist, never infer the intended task.
3. **Read STATUS.md before classifying workflow or deciding the next action.**
4. Restore workflow from `STATUS.md → Workflow.Type`.
   - Do not reclassify an existing task on every invocation.
   - A workflow-type change requires an explicit Lead decision recorded in STATUS history.
5. Determine invocation mode from STATUS and the request: planning, plan rework, implementation, implementation rework, review, re-review, or final acceptance.
6. Determine runtime: Codex, Pi, or generic.
7. Load the matching role file, the workflow recorded in STATUS, runtime adapter, and Warp adapter when applicable.
8. Perform only actions allowed by the Lifecycle Transition Table.
9. After a lifecycle transition, update STATUS.md first, then refresh INDEX.md.

### New task

For a new task:

1. Use Lead role.
2. Select workflow once: standard, complex, or bugfix.
3. Establish Control Plane / Code Plane separation.
4. Verify the Code Plane has a stable clean starting point.
5. Freeze `Task Baseline SHA = git rev-parse HEAD`.
6. Create Task ID and task workspace.
7. Create TASK.md and STATUS.md with the selected workflow and baseline.
8. Continue according to the Lifecycle Transition Table.

## Short Interaction Protocol

The user should not have to repeat the full protocol on every handoff.

### Session Role Binding

At the beginning of a new agent session or Warp pane, bind the role once.

Examples:

```text
Use multi-agent-development-workflow.
Role: Lead.
```

```text
Use multi-agent-development-workflow.
Role: Impl.
```

```text
Use multi-agent-development-workflow.
Role: Review.
```

The role remains the default for that conversation/session until explicitly changed. A fresh session must bind its role again unless the runtime provides an equivalent persistent role configuration.

### Short Commands

After role binding, accept concise user commands.

#### Lead

```text
新建任务：<requirement>
New task: <requirement>
```

Create a new Task using the New Task invocation protocol.

```text
继续 TASK-...
Continue TASK-...
```

Read STATUS first, determine the next legal Lead action from the Transition Table, load only the required artifacts, execute that action, and stop at the next role handoff boundary.

```text
验收 TASK-...
Accept TASK-...
```

Perform final acceptance only when lifecycle state permits it.

#### Impl

```text
继续 TASK-...
Continue TASK-...
```

Read STATUS first and perform the current legal Impl action:
- planning / plan rework → create the next Plan artifact;
- implementing / rework implementation → implement, test, commit Code Plane changes, and create the next IMPL artifact.

Stop when Lead action is required.

#### Review

```text
Review TASK-...
审核 TASK-...
```

Read STATUS first, verify the exact clean Review Target, perform independent Review, and create the next REVIEW artifact.

Stop after Review evidence is produced. Do not perform Lead transitions.

### Task omission

The Task ID may be omitted only when it is unambiguous:

- the current session already has one explicitly bound Task; or
- INDEX shows exactly one active Task compatible with the current role/action.

Then commands such as:

```text
继续
Review
验收
```

may resolve to that Task.

If multiple candidate Tasks exist, do not guess. Ask for or require the Task ID.

### Automatic command resolution

For every short command:

1. use the session-bound role;
2. resolve the Task ID;
3. read STATUS.md first;
4. restore Workflow.Type from STATUS;
5. locate the current Plan / IMPL / Review references from STATUS;
6. determine the single next legal action from the Transition Table;
7. execute only that role's work;
8. stop at the next handoff boundary;
9. return a concise handoff summary.

The user should not need to restate:
- Control Plane path when it can be derived from Task ID;
- current lifecycle state;
- current Plan/IMPL/Review round;
- Git snapshot fields already recorded in STATUS/IMPL;
- protocol rules already defined by this Skill.

### Handoff summary

At the end of a short-command action, respond concisely with:

```text
Task: <TASK-ID>
Completed: <what this role completed>
State: <current lifecycle state>
Artifact: <created/updated artifact>
Next: <Lead | Impl | Review> — <short action>
```

This summary is for the user. The next Agent must still recover authoritative state from STATUS and artifacts rather than trusting the summary alone.

## Core rule

- **What should be built?** → Lead
- **How should it be built?** → Impl
- **Was it built correctly?** → Review

Impl cannot approve itself.
Review cannot redefine requirements.
Only Lead can accept.

## Default Control Root

The default Control Plane location is always inside the current Code Plane project:

```text
<project-root>/.agent-team/
```

Resolve `<project-root>` with:

```bash
git rev-parse --show-toplevel
```

Then use:

```text
<project-root>/.agent-team/
├── INDEX.md
└── tasks/
```

Rules:

1. For a normal single-project workflow, create and use `.agent-team/` under the current project's Git root.
2. Do **not** automatically place Control Plane data under `/tmp`, `/private/tmp`, the user's home directory, or another global cache location.
3. An external Control Root is allowed only when:
   - the user explicitly requests it; or
   - an explicit configuration such as `AGENT_TEAM_DIR` points to it.
4. If `AGENT_TEAM_DIR` is not explicitly configured, project-local `.agent-team/` wins.
5. The project-local `.agent-team/` must remain excluded from Code Plane Git tracking, normally through `.git/info/exclude`.
6. All roles working on the same Task must resolve to the same canonical Control Root.
7. If an older task was created in a temporary external location and the user requests project-local storage, Lead should move/copy the complete Control Plane task namespace into `<project-root>/.agent-team/`, update references, and continue from the project-local copy.

Recommended initialization:

```bash
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
mkdir -p "$PROJECT_ROOT/.agent-team/tasks"
grep -qxF ".agent-team/" "$PROJECT_ROOT/.git/info/exclude" 2>/dev/null \
  || printf "\n.agent-team/\n" >> "$PROJECT_ROOT/.git/info/exclude"
```

## Control Plane and Code Plane

### Control Plane

Workflow metadata:

- INDEX.md
- TASK.md
- STATUS.md
- PLAN-vNNN.md
- IMPL-NNN.md
- REVIEW-NNN.md
- ACCEPTANCE.md

### Code Plane

The repository content whose behavior is being changed and reviewed, including relevant:

- production source;
- tests;
- migrations;
- resources;
- runtime/build configuration;
- other tracked project files.

### Separation invariant

Control Plane artifacts **MUST NOT be included in the reviewed Code Plane Git snapshot**.

The reviewed `Code Head SHA` must not change merely because a workflow artifact was created or updated.

Preferred setups:

1. **Default:** use `<project-root>/.agent-team/` and exclude it from Git with `.git/info/exclude`.
2. **Multiple worktrees / concurrent agents:** still prefer the primary project checkout's `.agent-team/` as the canonical Control Root; other worktrees should point to that same directory. Use an external Control Root only when explicitly configured.
3. **Versioned workflow metadata:** if artifacts must be versioned, store them in a separate control repository or other storage that does not alter Code Plane commits.

Do not force-add Control Plane artifacts to the Code Plane branch.

Before using an in-project `.agent-team/`, verify:

```bash
git ls-files .agent-team
git check-ignore -q .agent-team/
```

`git ls-files .agent-team` should return nothing.

If Control Plane files are already tracked in the Code Plane, migrate them out of the reviewed history/index before relying on this protocol.

## Task workspace

```text
.agent-team/
├── INDEX.md
└── tasks/
    └── TASK-YYYYMMDD-NNN-short-name/
        ├── TASK.md
        ├── STATUS.md
        ├── plans/
        ├── implementations/
        ├── reviews/
        └── ACCEPTANCE.md
```

By default the Control Root is `<project-root>/.agent-team/`. An external Control Root is opt-in, not automatic.

## Sources of truth

- TASK.md = requirement source of truth.
- approved PLAN-vNNN.md = implementation-intent source of truth.
- Code Head SHA = implementation source of truth.
- REVIEW-NNN.md = verification evidence.
- STATUS.md = only lifecycle source of truth.
- ACCEPTANCE.md = final closure evidence.
- INDEX.md = derived dashboard only.
- conversation history = supporting context only.

Artifact-local fields never override STATUS lifecycle state.

## Task baseline and implementation snapshots

At task creation Lead freezes:

```text
Task Baseline SHA: <code-plane sha>
```

It does not change for the lifetime of the task.

Each IMPL round records:

```text
Task Baseline SHA: <task start>
Previous Head SHA: <previous submitted implementation head>
Code Head SHA: <current submitted implementation head>
```

For IMPL-001:

```text
Previous Head SHA = Task Baseline SHA
```

For IMPL-002+:

```text
Previous Head SHA = previous IMPL round Code Head SHA
```

Review uses:

- `Task Baseline SHA → Code Head SHA` for full-task impact;
- `Previous Head SHA → Code Head SHA` for current-round changes.

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

Lead is the lifecycle transition authority. Impl and Review create evidence/artifacts; Lead validates the handoff and changes STATUS.

## Lifecycle Transition Table

| Current | Actor | Action / evidence | Next |
|---|---|---|---|
| CREATED | Lead | start normal planning | PLANNING |
| CREATED | Lead | confirm ALL trivial-task criteria and skip Plan Gate | READY_FOR_IMPLEMENTATION |
| PLANNING | Impl | create next PLAN-vNNN | PLANNING |
| PLANNING | Lead | receive complete Plan for decision | PLAN_REVIEW |
| PLAN_REVIEW | Lead | approve Plan | READY_FOR_IMPLEMENTATION |
| PLAN_REVIEW | Lead | reject Plan | PLAN_REWORK |
| PLAN_REWORK | Impl | create next Plan version | PLAN_REWORK |
| PLAN_REWORK | Lead | receive next Plan for decision | PLAN_REVIEW |
| READY_FOR_IMPLEMENTATION | Lead | hand off approved/fast-path task | IMPLEMENTING |
| IMPLEMENTING | Impl | create committed IMPL-NNN evidence | IMPLEMENTING |
| IMPLEMENTING | Lead | validate snapshot/evidence | READY_FOR_REVIEW |
| IMPLEMENTING | Lead | accept material-deviation signal | PLAN_REWORK |
| READY_FOR_REVIEW | Lead | start independent Review | REVIEWING |
| REVIEWING | Review | create REVIEW-NNN evidence | REVIEWING |
| REVIEWING | Lead | validate Review FAIL | REWORK |
| REVIEWING | Lead | validate Review PASS | READY_FOR_FINAL_ACCEPTANCE |
| REVIEWING | Lead | reviewer environment mismatch only; reset Review environment | READY_FOR_REVIEW |
| REVIEWING | Lead | frozen Code Target was mutated / invalidated | REWORK |
| REWORK | Lead | hand confirmed RW items to Implementation | IMPLEMENTING |
| READY_FOR_FINAL_ACCEPTANCE | Lead | final acceptance succeeds and ACCEPTANCE.md exists | ACCEPTED |
| READY_FOR_FINAL_ACCEPTANCE | Lead | final acceptance finds blocking issue | REWORK |
| any non-terminal state | Lead | external dependency prevents progress | BLOCKED |
| BLOCKED | Lead | dependency resolved; restore recorded Resume State | <Resume State> |
| any non-terminal state | Lead | cancel task | CANCELLED |

ACCEPTED and CANCELLED are terminal unless an explicit new task is created.

STATUS.md must record `Resume State` when entering BLOCKED.

## Artifact history

Plan, implementation, and review artifacts are append-only:

- PLAN-v001.md, PLAN-v002.md, ...
- IMPL-001.md, IMPL-002.md, ...
- REVIEW-001.md, REVIEW-002.md, ...

Never edit an old artifact into a new version/round.

STATUS.md and INDEX.md are mutable projections.
TASK.md may be amended only by Lead with changes explicitly logged.

## Identifier uniqueness

Identifiers are task-global within their prefix and MUST NOT be reused inside the same Task namespace, even across Plan versions, implementation rounds, or review rounds.

Examples:

```text
PLAN-v001: PLAN-001, PLAN-002
PLAN-v002: PLAN-003, PLAN-004

IMPL-001: CHANGE-001
IMPL-002: CHANGE-002

REVIEW-001: REV-001
REVIEW-002: REV-002
```

The same planned test keeps its existing TEST ID when executed. A newly introduced test gets the next unused TEST-xxx ID.

Do not reset numbering when a new artifact version is created.

## Plan ownership and approval

- Plan Content Owner: Impl.
- Plan Approval Owner: Lead.

Impl creates PLAN-vNNN with Approval Status PENDING.
Lead may modify only the Approval block to record APPROVED or REWORK.

Once decided, freeze that Plan version.

## Plan Gate classification

A task may skip Plan Gate only when **ALL** are true:

- localized change;
- no database/schema/data migration;
- no public API/contract change;
- no security/auth/permission impact;
- no concurrency/synchronization impact;
- no architecture-boundary change;
- no cross-module behavioral change;
- low regression risk;
- easily reversible;
- small and directly understood from existing code.

If any item is false or uncertain, Plan Gate is REQUIRED.

Fast path still requires stable Code snapshot, independent Review, and final acceptance.

When Plan Gate is SKIPPED, downstream artifacts must record:

```text
Plan Gate: SKIPPED
Plan Reference: N/A
Plan Version: N/A
```

They must not invent PLAN-v001.

## Material Plan deviation

A deviation is material when it changes approved architecture/component boundaries, API/data/schema contracts, security/concurrency behavior, requirement scope, major data/state flow, migration/rollback strategy, test coverage strategy, or major risk assumptions.

Protocol:

```text
STOP implementation
 ↓
Lead STATUS → PLAN_REWORK
 ↓
Impl creates next Plan version
 ↓
Lead PLAN_REVIEW
 ↓
APPROVED
 ↓
continue
```

## Stable Review Target

Each implementation round must bind to a Code Plane snapshot:

```text
Task Baseline SHA: <sha>
Previous Head SHA: <sha>
Code Head SHA: <sha>
Code Working Tree: CLEAN
Control Plane Excluded: YES
Frozen: true
```

Before submission Impl must commit intended Code Plane changes.

After READY_FOR_REVIEW, Implementation must not mutate that submitted Code Head target. Any later Code Plane change creates a new implementation round.

## Review Target verification

Before substantive Review, verify all:

```bash
git rev-parse HEAD
git diff --quiet
git diff --cached --quiet
git status --porcelain
```

Requirements:

1. observed HEAD == declared Code Head SHA;
2. unstaged tracked diff is empty;
3. staged diff is empty;
4. `git status --porcelain` is empty for the Code Plane checkout;
5. Control Plane is excluded/ignored and therefore does not make the Code Plane dirty.

If any check fails, do not perform substantive review. Record protocol status `REVIEW_TARGET_MISMATCH`; no PASS/FAIL exists yet.

## Independent Review context

Review should start in a fresh execution context whenever supported.

MUST NOT rely on Impl private reasoning, implementation conversation history, or self-review conclusions as proof.

MAY consume TASK, approved Plan or fast-path marker, IMPL, exact Code snapshot, full-task diff, round diff, test evidence, and prior Reviews for re-review.

Principle: **share artifacts, not private reasoning**.

## Final acceptance

After validated Review PASS, Lead creates ACCEPTANCE.md bound to:

- Plan Gate status;
- accepted Plan reference or N/A;
- accepted IMPL round;
- accepted Review round;
- Task Baseline SHA;
- accepted Code Head SHA;
- REQ/AC verification;
- test evidence;
- residual risks.

Only then may STATUS become ACCEPTED.

## Workflow selection

Existing task: restore `Workflow.Type` from STATUS.md.
New task: select standard, complex, or bugfix once and record it in STATUS.md.

## Runtime and terminal adapters

Use adapters under `adapters/` and `runtimes/`. They may describe startup, tools, worktrees, subagents, RPC, Code Mode, or sandboxing but may not bypass protocol invariants.
