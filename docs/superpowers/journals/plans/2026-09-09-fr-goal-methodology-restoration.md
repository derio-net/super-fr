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

<!-- fr:journal kind=discovery scope=plan id=p3t3-reorder created=2026-09-09T10:04:16 phase=3 -->
### p3t3-reorder · discovery · P3.T3 reorder: brief rewiring prose landed in Phase 2 (phase 3)

The fr-goal §5 brief (pickup + spec + handoff) and executor handoff pointer were written with the Phase 2 prose batch so the token tripwires covered all four files at once. P3.T3 verified the narration against the shipped verb (scope/phase flags match) — no further prose change. no-refactor-because: narration already exact.

<!-- fr:journal kind=finding scope=plan id=p3-review-comment created=2026-09-09T10:08:02 phase=3 state=fixed -->
### p3-review-comment · finding [fixed] · review-phase P3: wrong read-resolve comment (phase 3)

The handoff comment claimed the plan read-resolves; only the journal does (the plan lookup is active-only, correctly — archived plans need no handoffs). Fixed the comment. State: fixed.

<!-- fr:journal kind=discovery scope=plan id=p4t3-order-slip created=2026-09-09T10:29:48 phase=4 -->
### p4t3-order-slip · discovery · P4.T3 order inversion noted (phase 4)

The granularity token test was written after its prose (should have been RED first). The test still guards future edits; noted as a process slip, not repeated. no-refactor-because: prose rewrap only.

<!-- fr:journal kind=discovery scope=plan id=p5t3-reorder created=2026-09-09T10:58:47 phase=5 -->
### p5t3-reorder · discovery · P5.T3 reorder: contract norms prose landed in Phase 2 (phase 5)

The five executor norms and their token tripwires were written with the Phase 2 prose batch (same reason as P3.T3: one tripwire sweep across all four files). Verified above: all five norm tokens asserted and passing. P5.T3's remaining content is this verification. no-refactor-because: prose already exact.

<!-- fr:journal kind=discovery scope=plan id=p5t4s2-clean created=2026-09-09T11:02:25 phase=5 -->
### p5t4s2-clean · discovery · P5.T4.S2 toy walk clean, no findings to fix (phase 5)

The 3-phase grouped walk passed first try (after a test-only spec-table fix): per-phase brief order, write-claim refusal, deliver cursor, 6 accounting snapshots, journal check clean. No product findings; nothing to fix. no-refactor-because: verification-only step.

<!-- fr:journal kind=finding scope=plan id=p5-review-retry-mark created=2026-09-09T11:11:28 phase=5 state=fixed -->
### p5-review-retry-mark · finding [fixed] · review-phase P5: stale failed mark on retry (phase 5)

Self-review of the Phase 5 diff: setdefault left a retried failed unit reading failed while outstanding. Unconditional running mark on dispatch. State: fixed.

<!-- fr:journal kind=discovery scope=plan id=tool-version-discovery created=2026-09-09T11:52:34 phase=5 -->
### tool-version-discovery · discovery · Orchestration ran on tool fr 4.1.1, verification on worktree 4.2.0 (phase 5)

Discovery during review: workspace fr resolves to the tool-installed 4.1.1, not the worktree build. All plan/journal/acceptance/run orchestration therefore ran on stable pre-change tooling (desirable while building new tooling); every new behavior was verified under pytest against worktree code, and deliver gates re-run here on uv run fr 4.2.0. Consequence: this run's own cursor (fr-goal@1 flat) will drift-refuse against the new grouped shape — correct behavior, demonstrated live below.

<!-- fr:journal kind=discovery scope=plan id=own-run-drift-demo created=2026-09-09T11:52:59 phase=5 -->
### own-run-drift-demo · discovery · Own run drift-refuses against the new shape, as designed (phase 5)

Resolving implement on run 2026-09-09-feat-issue-464 (started fr-goal@1 flat) under the grouped shape refuses with removed: review. Correct: the cursor was computed for a step list that no longer exists. Plan-phase completion states (all 5 complete via fr plan edit) are the durable progress record; the run file stays as history. Live demonstration that flat-to-grouped migration refuses instead of silently advancing.
