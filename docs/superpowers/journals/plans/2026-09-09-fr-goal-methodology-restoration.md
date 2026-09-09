# Journal: 2026-09-09-fr-goal-methodology-restoration

<!-- fr:journal kind=discovery scope=plan id=p1t1s3-norefactor created=2026-09-09T08:44:51 phase=1 -->
### p1t1s3-norefactor · discovery · P1.T1.S3 no-refactor-because: single additive field (phase 1)

The Step.steps addition is one field plus a comment pointing at check.py for semantics. No duplication introduced, no naming to clean. Skipping an empty refactor step per fr-plan's omit-when-nothing rule.

<!-- fr:journal kind=finding scope=plan id=p1-review-emits-owner created=2026-09-09T09:22:31 phase=1 state=fixed -->
### p1-review-emits-owner · finding [fixed] · review-phase P1: emits_owner hole for no-emits top-level steps (phase 1)

Self-review of the Phase 1 diff: emits_owner fell back to parent (None) for a top-level step declaring no emits, silently recording --emitted keys nothing reads. Fixed (top-level always validates against its own emits) with a RED-first pin. State: fixed.

<!-- fr:journal kind=finding scope=plan id=p2-review-archived-journal created=2026-09-09T09:42:10 phase=2 state=fixed -->
### p2-review-archived-journal · finding [fixed] · review-phase P2: journal lookups ignored archived journals (phase 2)

Self-review of the Phase 2 diff: _skeleton_overridden and _refactor_justifications read the active journal path only, while render/check resolve archived journals too. Fixed to resolve_journal_read_path with an archival pinning test. State: fixed.
