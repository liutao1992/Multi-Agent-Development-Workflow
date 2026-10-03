# Codex Runtime Adapter

Core protocol is defined by SKILL.md.

## Warp mapping

- Left → Codex Lead
- Right top → Codex Implementation
- Right bottom → Codex Review

## Control Plane

Do not include .agent-team workflow artifacts in Code Plane commits. Use an ignored local Control Root or an external shared Control Root.

## Review isolation

Prefer a fresh Codex Review session/context.

Give Review artifacts plus Task Baseline SHA, Previous Head SHA, and exact Code Head SHA. Do not provide Implementation private reasoning as proof.

Review should inspect the exact clean Code Head snapshot and both full-task and current-round diffs.

## Subagents

Codex subagents/delegation may implement logical roles, but STATUS transitions remain Lead-controlled and protocol gates remain mandatory.
