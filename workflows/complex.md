# Complex Workflow

Use when architecture, migration, security, concurrency, API/contract, cross-module behavior, major refactor, or high regression risk is involved.

Plan Gate is mandatory.

PLAN should cover relevant architecture impact, migration/rollback, compatibility, failure modes, data integrity, observability, security/concurrency, tests, and rollout.

Any material deviation requires STOP → new Plan version → Lead approval.

Implementation must produce a committed stable Review Target.

Review must use a fresh context when supported and verify both local correctness and system-level impact against the exact Head SHA.

Final closure requires ACCEPTANCE.md.
