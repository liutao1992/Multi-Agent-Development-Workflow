# Orchestrated worker brief

This is the bounded reading path for workers launched by `agent-team`. The full
`SKILL.md` remains authoritative. Read its entry map, your role file, this brief,
and `STATUS.md` before task work; open a further SKILL section only when the
current state needs it. Read only artifacts named in STATUS or the single new
artifact awaiting Lead consumption. Do not scan every historical round.

## Role boundary

- Lead alone changes STATUS, TASK contract, Plan Approval, INDEX, and ACCEPTANCE.
- Impl creates one new PLAN or IMPL artifact and commits implementation work.
- Review creates one new REVIEW artifact against the exact frozen Code Head.
- Execute one legal role action and return control to the orchestrator, including
  after an intermediate Lead transition. Direct shortcuts below count as one action.
  Never invoke `agent-team` recursively.

## State-specific evidence

| Worker and current state | Required task material |
|---|---|
| Lead, CREATED | TASK, STATUS; workflow choice and baseline |
| Impl, PLANNING or PLAN_REWORK | TASK, STATUS; prior Plan only for rework |
| Lead, PLANNING or PLAN_REWORK | STATUS, new PLAN, TASK contract |
| Lead, PLAN_REVIEW | STATUS, referenced PLAN, TASK contract |
| Lead, READY_FOR_IMPLEMENTATION or REWORK | STATUS, TASK, approved PLAN if required, confirmed RW IDs if rework |
| Impl, IMPLEMENTING | STATUS, TASK, approved PLAN if required, prior REVIEW only for rework |
| Lead, IMPLEMENTING | STATUS, new IMPL, TASK contract, clean Git HEAD |
| Lead, READY_FOR_REVIEW | STATUS, referenced IMPL, clean Git HEAD |
| Review, REVIEWING | STATUS, TASK, current IMPL, approved PLAN if required, exact Git diff |
| Lead, REVIEWING | STATUS, new REVIEW, current IMPL, TASK contract, clean Git HEAD |
| Lead, READY_FOR_FINAL_ACCEPTANCE | STATUS, current REVIEW and IMPL, TASK, clean Git HEAD |

When consuming evidence, update Artifact and numeric Round together (IMPL-001.md
or REVIEW-001.md means Round: 1); also copy the Review Result and Protocol Status.
`Artifact:` values in STATUS are filenames only, for example `IMPL-001.md`.
`Reviewed Implementation:` in REVIEW may be `IMPL-001` or `IMPL-001.md`.
All evidence records the current Task Contract Revision and Hash.
The worker prompt gives the candidate pending filename when available; validate
the artifact and record only its basename in STATUS. The orchestrator validates
the transition, so normal handoffs do not require reading validator source code.

## Lead shortcuts

After a valid new IMPL, Lead may freeze the exact target and transition directly
`IMPLEMENTING → REVIEWING`. After a PASS REVIEW, Lead may create ACCEPTANCE.md
and transition directly `REVIEWING → ACCEPTED`. Each direct route must satisfy
the same implementation, Review, Code Head, and acceptance checks as the two
original transitions. Use the intermediate state when a separate decision is
needed. The executable validator is the final gate.

For uncommon branches (Plan amendment, Review FAIL/mismatch, BLOCKED, or
cancel), consult the matching section and Lifecycle Transition Table in
`SKILL.md`; do not infer protocol from this brief alone.
