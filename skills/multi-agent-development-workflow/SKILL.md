---
name: multi-agent-development-workflow
description: Use for non-trivial software-development tasks that need tmux-native multi-agent coordination, task definition, plan approval, implementation, independent review, rework, stable Git code snapshots, lifecycle control, and final acceptance across Pi, Codex, or other terminal coding-agent runtimes.
---

# Multi-Agent Development Workflow

## Purpose

This skill defines a deterministic, runtime-independent development protocol using three logical roles:

1. **Lead** — requirements, lifecycle control, plan approval, rework decisions, final acceptance.
2. **Impl** — investigation, planning, implementation, testing, immutable implementation-round evidence.
3. **Review** — fresh-context independent verification of an exact Code Plane Git snapshot.

Only Lead may declare a task **ACCEPTED**.

## Role Entry Map

Every agent must explicitly map its bound role to the corresponding role file before doing task work.

| Bound Role | Role File | Primary Responsibility |
|---|---|---|
| Lead | `roles/lead.md` | Task definition, lifecycle transitions, Plan approval, rework, final acceptance |
| Impl | `roles/impl.md` | Investigation, Plan creation, implementation, tests, IMPL evidence |
| Review | `roles/review.md` | Independent verification, review tests, REVIEW evidence |

Role files are resolved relative to this Skill's directory.

Required startup order:

```text
SKILL.md
  ↓
roles/<role>.md
  ↓
<project-root>/.agent-team/tasks/<TASK-ID>/STATUS.md
  ↓
task artifacts required by current state
```

Do not perform role-specific task work before loading the matching role file.

For `Invocation Mode: Orchestrated Worker`, the bounded startup path is this
entry map, the matching role file, `automation/worker-brief.md`, and STATUS.
Open further sections of this Skill only for the current state's requirements.

### Where each role finds the current task material

Given:

```text
TASK_ROOT=<project-root>/.agent-team/tasks/<TASK-ID>/
```

**Lead reads:**

```text
TASK_ROOT/STATUS.md                ← always first
TASK_ROOT/TASK.md                  ← requirements
TASK_ROOT/plans/PLAN-vNNN.md       ← Plan awaiting approval / accepted Plan
TASK_ROOT/implementations/IMPL-NNN.md
TASK_ROOT/reviews/REVIEW-NNN.md
TASK_ROOT/ACCEPTANCE.md            ← final closure
```

Lead chooses the exact Plan / IMPL / Review artifact from references recorded in `STATUS.md`; do not guess the latest file by filename alone.

In `STATUS.md`, each `Artifact:` field under Current Plan, Current Implementation,
Current Review, or Final Acceptance contains only the filename, such as
`IMPL-001.md`. The artifact directory is determined by the section; do not put
`implementations/`, `plans/`, or `reviews/` in the field value.

**Impl reads:**

```text
TASK_ROOT/STATUS.md                ← always first
TASK_ROOT/TASK.md                  ← requirements
TASK_ROOT/plans/PLAN-vNNN.md       ← approved implementation plan, when Plan Gate is REQUIRED
TASK_ROOT/reviews/REVIEW-NNN.md    ← previous failed review, when in REWORK
```

When `Plan Gate: SKIPPED`, no Plan file exists and Impl must use `TASK.md + STATUS.md`.

**Review reads:**

```text
TASK_ROOT/STATUS.md                ← always first
TASK_ROOT/TASK.md                  ← requirements / acceptance criteria
TASK_ROOT/plans/PLAN-vNNN.md       ← approved plan, or N/A on fast path
TASK_ROOT/implementations/IMPL-NNN.md ← exact implementation round under review
TASK_ROOT/reviews/REVIEW-NNN.md    ← prior review only for re-review context
```

Review must use the exact artifact references and Code Head SHA recorded in `STATUS.md` / `IMPL-NNN.md`.

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
7. Load the matching role file explicitly: Lead → `roles/lead.md`, Impl → `roles/impl.md`, Review → `roles/review.md`; then load the workflow recorded in STATUS, runtime adapter, and tmux adapter when applicable.
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

## Automatic Orchestration

The default interactive execution model is **tmux-native orchestration**.

Automatic orchestration does not change lifecycle authority:

- Lead remains the only role allowed to transition `STATUS.md`;
- Impl creates Plan / implementation evidence but does not transition lifecycle state;
- Review creates independent Review evidence but does not transition lifecycle state;
- tmux is transport/synchronization only; it is not a fourth decision-making role.

Default topology:

```text
User
 ↓
Lead = project-scoped tmux pane
 ├─ Impl pane
 └─ Review pane
```

The user talks only to Lead. Lead delegates through tmux until ACCEPTED, CANCELLED,
BLOCKED, or a genuine human/product decision is required.

### Preferred transport: tmux-native

Use one project-scoped tmux session with three role panes. The bundled launcher is:

```bash
madw start
```

The launcher derives the session from the canonical Git root:

```text
madw-<repo-name>-<path-hash>
└── team
    ├── Lead
    ├── Impl
    └── Review
```

This prevents unrelated projects from reusing global `leader/impl/review`
sessions.

tmux owns only:

```text
role addressing
message delivery
completion synchronization
terminal observability
```

`.agent-team/` remains the durable lifecycle/evidence source of truth.

Use bounded handoffs:

```bash
madw send impl "<Task ID + action + STATUS/artifact references>"
madw wait impl TASK-... 001

madw restart review
madw send review "<Task ID + exact IMPL/head + STATUS references>"
madw wait review TASK-... 001
```

Workers signal only after writing their immutable artifact:

```bash
madw signal impl TASK-... 001
madw signal review TASK-... 001
```

`madw wait` wraps `tmux wait-for` with timeout, dead-pane detection, recent
output capture, and expected-artifact hash verification. Completion is recorded
in the project's tmux session so a repeated wait can verify the same artifact.
A completion signal never authorizes a lifecycle transition by itself; Lead
must validate the artifact and Code Plane evidence. The tmux launcher does not
run the standalone Python Orchestrator's per-transition validators.

Impl may keep its context across Plan, implementation and confirmed rework.
Before every substantive Review round, Lead MUST refresh Review with
`madw restart review` (or an equivalent runtime-native new-conversation
operation) so Review does not inherit prior private context.

The standalone `scripts/agent-team` Python Orchestrator remains a **process
fallback** for CI/unattended execution. It is not the communication layer for
the interactive tmux team.

### Code Plane concurrency invariant

Automatic orchestration MUST serialize mutable work by working tree:

```text
one Git working tree = at most one automated Task at a time
```

A Task-level lock is not sufficient because HEAD, index, and working tree are shared resources.

Standalone Process fallback MUST hold a Code Plane lock for the full Task run, including Task creation. Tmux-native Lead MUST obey the same invariant and serialize mutable work in the shared working tree.

Parallel automated Tasks require separate Git worktrees.

### Programmatic role postconditions

The standalone Process fallback MUST validate role boundaries after every worker action. Tmux-native Lead MUST enforce the same postconditions before advancing STATUS.

- **Planning Impl:** Code Plane unchanged; STATUS/TASK unchanged; existing immutable artifacts unchanged; exactly one new PLAN.
- **Implementation Impl:** STATUS/TASK unchanged; existing immutable artifacts unchanged; exactly one new IMPL; Code Plane clean after commit; IMPL Code Head matches observed HEAD.
- **Review:** Code Plane HEAD/index/worktree unchanged; STATUS/TASK unchanged; existing immutable artifacts unchanged; exactly one new REVIEW.
- **Lead:** Code Plane unchanged; existing IMPL/REVIEW immutable; no role-owned artifacts created.

A postcondition violation is a protocol failure. Stop orchestration rather than advancing STATUS.

### Executable lifecycle state machine

For the standalone Process fallback, the Lifecycle Transition Table is a programmatic invariant, not prompt-only guidance. Tmux-native Lead must preserve the same evidence requirements.

After each Lead action the runtime MUST validate:

1. `before_state → after_state` is an allowed transition;
2. transition-specific evidence exists;
3. artifact references resolve to real files;
4. Code Head references use the full 40-character SHA where required.

Required evidence includes at least:

- Plan Gate skip reason for the fast path;
- PENDING Plan before entering PLAN_REVIEW;
- APPROVED / REWORK recorded consistently in STATUS and Plan artifact;
- approved Plan before implementation when Plan Gate is REQUIRED;
- frozen implementation target and exact STATUS/IMPL/observed Code Head match before Review;
- Review PASS before READY_FOR_FINAL_ACCEPTANCE, with machine-verifiable Review target evidence and matching Task Contract;
- the current observed Git HEAD still equal to the reviewed implementation head at READY_FOR_FINAL_ACCEPTANCE and ACCEPTED;
- Review FAIL before REWORK only when STATUS and REVIEW both declare FAIL, the Review targets the current IMPL/Code Head, and at least one blocking REV issue exists;
- REVIEW_TARGET_MISMATCH only when STATUS and REVIEW both declare protocol mismatch with Result N/A and declared/observed heads match submitted/current Git state;
- confirmed RW IDs before rework implementation;
- ACCEPTANCE.md, PASS Review, matching Accepted Code Head, and current observed Git HEAD before ACCEPTED;
- Resume State equal to the prior state when entering BLOCKED.

Illegal jumps such as `CREATED → ACCEPTED` MUST fail with a protocol violation.

### Task Contract revision and hash

`TASK.md` is the Requirement Source of Truth, but executable evidence MUST bind a specific immutable requirement snapshot.

The Task Contract consists of:

- Objective;
- Requirements;
- Acceptance Criteria;
- Constraints;
- Dependencies;
- Out of Scope.

TASK MUST record:

```text
Task Contract Revision: <integer >= 1>
Task Contract Hash: <64-char SHA-256>
```

STATUS MUST record the same revision/hash.

Every active Plan, IMPL, REVIEW and ACCEPTANCE artifact MUST carry the same Task Contract Revision/Hash.

When Lead changes any Task Contract section:

1. increment Revision exactly once;
2. recompute and record the new Hash;
3. append Requirement Change Log evidence with Revision, Previous Hash and New Hash;
4. if a prior Plan / IMPL / REVIEW exists, transition to `PLAN_REWORK`;
5. do not reuse evidence bound to the old Task Contract.

A Task Contract amendment invalidates old planning, implementation review, and acceptance evidence.

During `PLAN_REVIEW`, an amendment moves to `PLAN_REWORK` while the pending old Plan remains unchanged and referenced for history. The next Impl Plan version must bind the new contract; the invalidated Plan does not receive a REWORK approval decision.

`Rework Requirements` contains Review remediation instructions and is excluded from the requirement hash. Lead may update only that TASK section during `REVIEWING -> REWORK`, with valid FAIL or MISMATCH evidence. Contract revision/hash and all other TASK content remain unchanged. Product requirement changes still require a contract amendment and `PLAN_REWORK`.

### Plan content immutability

For existing `PLAN-vNNN.md` artifacts:

- Impl owns Plan content;
- Lead owns only the `## Approval` block.

The standalone Process fallback MUST hash/compare Plan content with the Approval block excluded. For Plans created with a top-level `Approval Status:` line, that one line is also treated as approval metadata during comparison; all other Plan content remains immutable. New Plans place the status inside `## Approval` as the template specifies.

Lead approval MUST NOT change Scope, Implementation Steps, Testing Plan, Risks, Open Questions, or other Plan content.

Only the current Plan in `PLAN_REVIEW` may change its Approval block, and only from:

```text
PENDING → APPROVED
PENDING → REWORK
```

After the decision, the whole Plan version is immutable, including the Approval block.

Before `PLANNING / PLAN_REWORK → PLAN_REVIEW`, both STATUS and the Plan artifact MUST record `PENDING`. This prevents Impl from self-approving its own Plan.

### Whole Control Plane write boundary

Role postconditions cover the whole project Control Plane, excluding `runtime/`.

Allowed durable writes:

- **Lead:** current Task Lead-owned projections/artifacts plus `INDEX.md`;
- **Planning Impl:** exactly the new Plan artifact for the current Task;
- **Implementation Impl:** exactly the new IMPL artifact for the current Task, plus permitted Code Plane implementation changes;
- **Review:** exactly the new REVIEW artifact for the current Task.

No role may modify another Task namespace.

Task bootstrap may create only the new Task's `TASK.md` / `STATUS.md` and update/create `INDEX.md`.

### Automatic lifecycle driver

Lead in tmux-native mode (or the standalone Orchestrator in process fallback) repeatedly reads:

```text
<project-root>/.agent-team/tasks/<TASK-ID>/STATUS.md
```

and dispatches one role action at a time.

Core selection rules:

| Lifecycle state | Condition | Dispatch |
|---|---|---|
| CREATED | always | Lead |
| PLANNING | no unrecorded new Plan artifact | Impl |
| PLANNING | a new Plan exists but STATUS has not consumed it | Lead |
| PLAN_REVIEW | always | Lead |
| PLAN_REWORK | no unrecorded next Plan | Impl |
| PLAN_REWORK | next Plan exists | Lead |
| READY_FOR_IMPLEMENTATION | always | Lead |
| IMPLEMENTING | no unrecorded new IMPL artifact | Impl |
| IMPLEMENTING | new IMPL exists | Lead |
| READY_FOR_REVIEW | always | Lead |
| REVIEWING | no unrecorded new REVIEW artifact | Review |
| REVIEWING | new REVIEW exists | Lead |
| REWORK | always | Lead |
| READY_FOR_FINAL_ACCEPTANCE | always | Lead |
| ACCEPTED / CANCELLED / BLOCKED | terminal for current run | stop |

Filename scanning is used only as a **handoff readiness signal**. It does not replace STATUS as lifecycle truth and does not authorize an agent to guess which artifact should be executed against. Lead still records the authoritative artifact reference in STATUS.

### Orchestrated Worker contract

Workers invoked by the Orchestrator receive:

```text
Invocation Mode: Orchestrated Worker
```

An orchestrated worker MUST:

1. execute exactly one legal role action;
2. read STATUS first;
3. use the role file and referenced artifacts;
4. stop at the next handoff boundary;
5. never start another Orchestrator recursively;
6. preserve role boundaries.

Lead may use the direct `IMPLEMENTING → REVIEWING` and `REVIEWING → ACCEPTED`
transitions to combine adjacent decisions in one invocation. The executable
validator checks all evidence required by both original gates. The original
intermediate states remain valid when a separate decision is needed.

Impl and Review MUST NOT rewrite lifecycle state in STATUS. Their newly created immutable artifact is the signal that Lead should run next.

### Commands

Start the visible project-scoped team:

```bash
madw start
```

Inspect or watch it:

```bash
madw status
madw watch
```

tmux 底部状态栏显示项目工作目录、Git 分支、当前任务和 STATUS 阶段，以及
Lead/Impl/Review 的交接方向。`madw send`、`wait`、`signal` 负责更新它；
这是 tmux 界面信息，不要把同样的进度横幅重复发送给 Agent 或写入对话上下文。

在 MADW 三面板界面按 `Ctrl+C` 会停止整个项目团队，结束 Leader、Impl、Review
及其 tmux session。仅需暂时离开时按 `Ctrl+b d`，之后用 `madw watch`
重新进入；也可在普通终端执行 `madw stop`。不要把 `Ctrl+C` 当作单个
Agent 的任务中断键。

Lead handoff helpers:

```bash
madw send impl "<handoff>"
madw wait impl TASK-... 001

madw restart review
madw send review "<handoff>"
madw wait review TASK-... 001
```

Environment/preflight:

```bash
madw doctor
```

For CI/unattended process fallback:

```bash
agent-team --runtime codex --transport process start "Add persistent AI chat history"
agent-team --runtime codex --transport process run TASK-YYYYMMDD-NNN-short-name
agent-team metrics TASK-YYYYMMDD-NNN-short-name
```

### BLOCKED resume entry

`BLOCKED` intentionally stops ordinary standalone `run`.

Resume requires an explicit Lead entry:

```bash
agent-team --runtime codex resume <TASK-ID> "<human decision>"
```

The resume worker MUST:

1. read BLOCKED STATUS and recorded Resume State;
2. consume the human resolution;
3. persist the human decision in STATUS → `Blocked Resolution` with resolution metadata;
4. modify no Code Plane content;
5. transition exactly `BLOCKED → <Resume State>`, or CANCELLED when explicitly requested;
6. pass the normal Lead write-boundary, Task Contract and transition validators;
7. then continue the automatic lifecycle.

This makes BLOCKED recovery explicit and auditable.

### Process fallback transport

Default transport:

```bash
agent-team --runtime codex --transport process run <TASK-ID>
```

The standalone Orchestrator starts headless role workers itself. Use this for CI/unattended execution, not as the interactive tmux team's transport.

### tmux three-pane transport

The normal interactive workflow is:

```text
┌───────────────────┬──────────────────┐
│                   │ Impl             │
│ Lead              ├──────────────────┤
│                   │ Review           │
└───────────────────┴──────────────────┘
```

`madw start` performs preflight before creating panes: Git repository, Skill
installation, tmux, and Agent runtime. Runtime selection is explicit argument,
then `MADW_RUNTIME`, then installed Pi, then installed Codex.

The launcher does not depend on a blind fixed `sleep 1`; it verifies pane
process startup up to a configurable boot timeout and removes a partial team on
failure.

Review freshness uses `tmux respawn-pane -k` through `madw restart review`,
which keeps the pane address/layout stable while replacing the Review Agent
context.

No project-defined Queue, mailbox, heartbeat, lease, claim, quarantine, or
`agent-team worker Impl/Review` communication layer is used in tmux-native mode.

### Stop conditions

Automatic execution stops instead of guessing when:

- STATUS becomes BLOCKED;
- a worker completes without producing protocol progress;
- a required runtime is unavailable;
- a tmux role pane / Agent process disappears while a handoff is pending;
- a genuine human/product decision is required;
- maximum orchestration steps are exceeded.

This preserves human authority at ambiguity boundaries while removing routine handoff work.

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
| IMPLEMENTING | Lead | validate and freeze implementation target; start independent Review immediately | REVIEWING |
| IMPLEMENTING | Lead | accept material-deviation signal | PLAN_REWORK |
| READY_FOR_REVIEW | Lead | start independent Review | REVIEWING |
| REVIEWING | Review | create REVIEW-NNN evidence | REVIEWING |
| REVIEWING | Lead | validate Review FAIL | REWORK |
| REVIEWING | Lead | validate Review PASS | READY_FOR_FINAL_ACCEPTANCE |
| REVIEWING | Lead | validate Review PASS and final acceptance; create ACCEPTANCE.md | ACCEPTED |
| REVIEWING | Lead | reviewer environment mismatch only; reset Review environment | READY_FOR_REVIEW |
| REVIEWING | Lead | frozen Code Target was mutated / invalidated | REWORK |
| REWORK | Lead | hand confirmed RW items to Impl | IMPLEMENTING |
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

After READY_FOR_REVIEW, Impl must not mutate that submitted Code Head target. Any later Code Plane change creates a new implementation round.

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
