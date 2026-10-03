# Generic Runtime Adapter

Use this adapter for coding agents that do not have a dedicated runtime file.

## Requirements

The runtime should ideally provide:

- repository file access
- source editing
- command execution
- test execution
- independent sessions or logical agents

## Mapping

Create three logical roles:

```text
Lead
Implementation
Review
```

They may be:

- separate terminal sessions
- subagents
- separate processes
- remote workers
- logical roles managed by an orchestrator

## Minimum invariant

Regardless of runtime:

1. Lead defines TASK.md.
2. Implementation produces PLAN.md.
3. Lead approves the plan.
4. Implementation writes code and IMPLEMENTATION.md.
5. Review independently verifies and produces REVIEW.md.
6. Lead decides REWORK or ACCEPTED.

Do not allow runtime convenience to bypass these gates for substantial work.
