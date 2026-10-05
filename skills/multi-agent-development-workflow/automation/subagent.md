# Native SubAgent Orchestration

Native SubAgents are an optional runtime-specific alternative. The default
visible workflow on this branch is tmux-native:

```text
Lead pane → Impl pane / Review pane
```

If a host runtime explicitly uses native child-agent primitives, all core
protocol invariants remain unchanged: Lead-only lifecycle authority, Task
Contract binding, Plan ownership, stable clean Code Head, independent current-round
Review, PASS-before-acceptance, and final HEAD verification.

Native SubAgents must not introduce a second project-defined message queue.
For the normal three-Agent visible workflow, use `madw start`.
