# Pi Runtime Adapter

Use this file only for Pi-specific execution details.

The core workflow remains defined by SKILL.md.

## Suggested Warp mapping

```text
Left        → pi → Lead role
Right top   → pi → Implementation role
Right bottom→ pi → Review role
```

Load the corresponding file from `roles/` into each session.

## Code Mode

Code Mode can be useful for Implementation and Review because they often need to compose multiple file, shell, search, diff, and test operations.

Prefer enabling Code Mode without changing the role protocol.

Code Mode is an execution mechanism, not a replacement for:

- task separation
- plan approval
- independent review

## Future automation

Pi RPC / SDK may automate handoffs later.

Automation must still preserve:

```text
Lead
 ↓
Implementation
 ↓
Review
 ↓
Lead
```

Do not let automation remove the independent Review gate.
