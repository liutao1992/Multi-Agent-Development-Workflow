# Codex Runtime Adapter

Core protocol is defined by SKILL.md.

## Warp mapping

- Left → Codex Lead
- Right top → Codex Implementation
- Right bottom → Codex Review

## Review isolation

Prefer a fresh Codex review session/context.

Give Review artifacts and exact Git target, not Implementation private reasoning.

## Git target

Implementation submits a committed Head SHA. Review checks out or inspects that exact SHA.

A moving branch name is not sufficient. New code changes require a new implementation round.

## Subagents

Codex subagents/delegation may implement logical roles but must preserve lifecycle control, Plan Gate, stable Head SHA, independent Review, and Lead Acceptance.
