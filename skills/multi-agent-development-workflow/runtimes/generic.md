# Generic Runtime Adapter

Use three logical roles: Lead, Impl, Review.

Default Control Root:

```text
<project-root>/.agent-team/
```

Do not automatically use temporary/global directories. External Control Roots require explicit user or environment configuration.

Minimum invariants:


1. Lead defines TASK and controls STATUS.
2. Impl creates immutable Plan versions.
3. Lead approves Plan.
4. Impl commits Code Plane changes and creates IMPL-NNN bound to Task Baseline SHA, Previous Head SHA, and Code Head SHA.
5. Review starts independently, verifies the exact clean Code Head SHA, and inspects both the full-task diff and current-round diff.
6. Review creates immutable REVIEW-NNN.
7. Lead decides rework or final acceptance.
8. Lead creates ACCEPTANCE.md before STATUS becomes ACCEPTED.

Runtime convenience must not bypass these invariants.

## Automatic execution

The bundled executable Orchestrator currently provides concrete drivers for \`codex\` and \`pi\`.

Other runtimes may implement the same worker contract:

\`\`\`text
dispatch(role, taskId, action)
wait()
read STATUS
repeat until terminal
\`\`\`

A generic runtime adapter must not bypass Lead-only lifecycle transitions or independent Review.


## Preferred native SubAgent hierarchy

If the runtime exposes true parent/child agent collaboration, prefer:

\`\`\`text
Lead parent
├── reusable Impl child per Task
└── reusable Review child with current-round input verification
\`\`\`

Use runtime-native spawn/follow-up/wait/close primitives. A separate OS process is a process worker, not a SubAgent.

Fallback order:

\`\`\`text
tmux → native-subagent → process → manual
\`\`\`
