# Pi Runtime Adapter

Core protocol is defined by SKILL.md.

## Warp mapping

- Left → Pi Lead
- Right top → Pi Implementation
- Right bottom → Pi Review

## Code Mode

Code Mode may improve tool orchestration but does not replace Plan Gate, stable Git Review Target, independent Review, or Lead acceptance.

## Review isolation

Prefer a fresh Pi review session/context.

Share task artifacts, exact Plan version, IMPL round, Base/Head SHA, repository state, and test evidence. Do not provide private Implementation reasoning as proof.

## RPC / SDK automation

Pi RPC/SDK may automate handoffs, but orchestration must enforce STATUS as lifecycle truth, immutable rounds, frozen Head SHA, new round after code changes, and final ACCEPTANCE.md.
