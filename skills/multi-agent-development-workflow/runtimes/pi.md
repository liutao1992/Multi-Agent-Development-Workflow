# Pi Runtime Adapter

Core protocol is defined by SKILL.md.

## Warp mapping

- Left → Pi Lead
- Right top → Pi Impl
- Right bottom → Pi Review

## Control Plane

Keep workflow artifacts outside reviewed Code Plane history. Use an ignored local Control Root or an external shared Control Root.

## Code Mode

Code Mode may improve tool orchestration but does not replace lifecycle, Plan Gate, stable Code snapshots, independent Review, or Lead acceptance.

## Review isolation

Prefer a fresh Pi Review session/context.

Share artifacts plus Task Baseline SHA, Previous Head SHA, exact Code Head SHA, diffs, and test evidence. Do not share Impl private reasoning as proof.

## RPC / SDK

Automation must restore workflow from STATUS for existing tasks, obey the Transition Table, keep Control Plane separate, and create a new round after every submitted Code Plane change.
