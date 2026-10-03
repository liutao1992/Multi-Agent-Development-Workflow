# Native SubAgent Orchestration

## Model

Native mode treats the roles as a parent-child hierarchy:

\`\`\`text
Lead = Parent / Root
├── Impl = reusable child
└── Review = fresh child per round
\`\`\`

This is the preferred automation model when the current coding runtime exposes native subagent collaboration.

## Why Lead is the parent

The protocol already gives Lead exclusive authority over:

- Task creation;
- STATUS lifecycle transitions;
- Plan approval;
- rework confirmation;
- final acceptance.

Therefore the runtime hierarchy matches the protocol hierarchy.

## Impl reuse policy

Create one Impl SubAgent per Task when practical.

Reuse it for:

1. investigation and Plan;
2. implementation after Plan approval;
3. confirmed rework;
4. follow-up implementation rounds.

The reusable Impl identity is runtime/session metadata, not lifecycle truth. If it disappears, spawn a replacement and reconstruct from STATUS plus artifacts.

## Review freshness policy

Create a new Review SubAgent for every REVIEW-NNN.

Never reuse Review-1 to produce REVIEW-2.

A Review child receives bounded evidence only and must not inherit Impl private reasoning or the parent/Impl implementation conversation.

## Serial write policy

Impl and Review MUST NOT edit/review the same mutable working tree concurrently.

The parent sequence is:

\`\`\`text
Lead action
→ wait
→ Impl action
→ wait
→ Lead action
→ wait
→ fresh Review action
→ wait
→ Lead decision
\`\`\`

Subagents may parallelize read-only investigation internally only when that does not create conflicting writes or weaken Review independence.

## Coordination pseudocode

\`\`\`text
while task is non-terminal:
    state = read STATUS

    if Lead owns next action:
        Lead executes transition/action
        continue

    if Impl owns next action:
        if no live Impl child:
            impl = spawn(Impl, bounded task context)
        follow_up(impl, current TASK/STATUS/artifact references)
        wait(impl)
        continue

    if Review owns next action:
        review = spawn_fresh(Review, bounded review evidence)
        wait(review)
        close(review)
        continue
\`\`\`

## Context contract

### Impl child

May receive:

- TASK;
- STATUS;
- approved Plan;
- confirmed RW IDs;
- prior failed Review relevant to the rework;
- repository context.

### Review child

May receive:

- TASK;
- STATUS;
- approved Plan or N/A fast-path marker;
- exact IMPL round;
- Baseline / Previous / Code Head SHAs;
- full-task and current-round diffs;
- test evidence;
- prior Review only when re-review requires it.

Review must not receive Impl private reasoning as proof.

## Runtime fallback

If native subagents are unavailable:

\`\`\`text
native-subagent
     ↓ unavailable
process
     ↓ if visible Warp workers desired
queue
     ↓
manual
\`\`\`

The fallback changes execution mechanics only. It does not change lifecycle authority or artifacts.
