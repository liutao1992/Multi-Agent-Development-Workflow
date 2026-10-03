# Complex Workflow

Use when architecture, migration, security, concurrency, API/contract, cross-module behavior, major refactor, or high regression risk is involved.

Plan Gate is mandatory and may not be skipped.

Task Baseline SHA is frozen at task creation.

Every implementation round must provide Previous Head SHA and Code Head SHA.

Review must inspect both full-task diff and current-round diff and verify a clean exact Code Plane checkout.

Any material deviation requires STOP → PLAN_REWORK → next Plan version → Lead approval.

Final closure requires ACCEPTANCE.md bound to the exact accepted Code Head SHA.
