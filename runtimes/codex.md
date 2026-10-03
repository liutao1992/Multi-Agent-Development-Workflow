# Codex Runtime Adapter

Use this file only for Codex-specific execution details.

The core workflow remains defined by SKILL.md.

## Suggested Warp mapping

```text
Left         → codex → Lead role
Right top    → codex → Implementation role
Right bottom → codex → Review role
```

Load the corresponding file from `roles/` into each session.

## Isolation

When supported and useful, use separate worktrees or isolated agent environments.

The Implementation Agent should be the primary production-code writer.

The Review Agent should inspect a stable implementation state, preferably identified by a branch or commit when using isolated worktrees.

## Subagents

If Codex offers subagent/delegation functionality, it may be used to execute the logical roles.

Do not collapse role boundaries merely because the runtime can spawn agents.

The Lead still owns final acceptance.
