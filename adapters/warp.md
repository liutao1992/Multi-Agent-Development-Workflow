# Warp Adapter

Warp is the preferred human-visible control surface. It does not define lifecycle semantics.

## Default layout

```text
┌──────────────────────────────┬──────────────────────────────┐
│ Lead Agent                   │ Implementation Agent         │
│ Task / STATUS / Plan Gate    │ Plan / Code / Test           │
│ Rework / Acceptance          │ Stable Review Target         │
│                              ├──────────────────────────────┤
│                              │ Review Agent                 │
│                              │ Fresh Review / Exact SHA     │
└──────────────────────────────┴──────────────────────────────┘
```

Do not enable synchronized input.

## Shared working tree mode

Allowed only for sequential manual coordination.

- Lead: read-oriented.
- Implementation: production-code writer.
- Review: read-oriented.

Before Review:

1. Implementation commits intended changes.
2. Working tree is clean.
3. IMPL-NNN records Base SHA and Head SHA.
4. Lead sets READY_FOR_REVIEW.
5. Implementation stops modifying repository code until Review finishes.

Review verifies `git rev-parse HEAD` equals Head SHA and uses Base→Head diff.

Any code change during Review invalidates the target and requires a new round.

## Recommended concurrent mode

Prefer worktrees:

```text
project-main/
project-implementation/
project-review/
```

Review worktree should inspect the exact Head SHA, not only a branch name.

## Handoffs

Every handoff includes Task ID, directory, lifecycle state, artifact/version, and exact Head SHA for Review.
