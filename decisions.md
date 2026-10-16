# Decisions Log

Append-only audit trail of approvals, amendments, backward steps, and conditional-skip rationales. See [[state-persistence]] for schema.

## 2026-10-16T11:01:07Z · init · PROJECT_STATE.md migrated to the lifecycle schema

init-state migrated the pre-lifecycle PROJECT_STATE.md (issue #21).
The lifecycle header was prepended and the old body kept verbatim
below it. Phase 3.3 was deduced from git state: clean tree on
`4b435be`, with the last cycle already promoted to main on 2026-10-15.
Approved reads `pending` because no plan has been sealed with a
sha256 yet. The 2026-10-15 promotion entry stays where it was, at
the foot of PROJECT_STATE.md, so the body is unchanged.
