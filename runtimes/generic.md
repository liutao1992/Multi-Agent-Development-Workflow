# Generic Runtime Adapter

Use three logical roles: Lead, Impl, Review.

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
