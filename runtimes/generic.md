# Generic Runtime Adapter

Use three logical roles: Lead, Implementation, Review.

Minimum invariants:

1. Lead defines TASK and controls STATUS.
2. Implementation creates immutable Plan versions.
3. Lead approves Plan.
4. Implementation commits code and creates IMPL-NNN bound to Base/Head SHA.
5. Review starts independently and verifies exact Head SHA.
6. Review creates immutable REVIEW-NNN.
7. Lead decides rework or final acceptance.
8. Lead creates ACCEPTANCE.md before STATUS becomes ACCEPTED.

Runtime convenience must not bypass these invariants.
