# Journal: 2026-09-28-ui-visual-evidence

<!-- fr:journal kind=discovery scope=plan id=d7b368d68bb3 created=2026-09-28T20:00:54+00:00 phase=1 -->
### d7b368d68bb3 · discovery · AcceptanceItem.visual lands in P1.T2, not P1.T3 (phase 1)

The plan assigns `AcceptanceItem.visual` to P1.T3 ("record sections"), but `fr acceptance add --visual-state/--visual-interaction` (P1.T2) writes through `fr.record.apply`'s `_apply_rows` -> `apply_record`, which builds the matrix `Row` from an `AcceptanceItem`. The CLI cannot thread `visual` to the writer without the field existing on `AcceptanceItem`, so it was added in P1.T2 as necessary plumbing. P1.T3 then adds the record's own evidence section (`StepRecord.visual`: `VisualEvidence`/`VisualShot`) on top of it. No behavior gap — both tasks' RED tests are still real (P1.T3's record-apply test exercises a different code path, `fr.record.apply` directly rather than the CLI) — but a reader diffing task boundaries against the plan should know this before assuming P1.T3's diff is self-contained.

<!-- fr:journal kind=discovery scope=plan id=1eb2269f669e created=2026-09-28T20:00:54+00:00 phase=1 -->
### 1eb2269f669e · discovery · render_row_block did not emit verify-style optional fields generically (phase 1)

`fr.acceptance.edit.render_row_block` (the ONE place that renders a row block into matrix.yaml) had to be extended by hand for `visual`, the same way `verify` was added before it — there is no generic "render every optional field" loop, so a future optional `Row` field needs the same one-line addition here or it round-trips as `None` silently (caught in this phase only because the CLI round-trip test exercises it explicitly).

<!-- fr:journal kind=discovery scope=plan id=aaa7162b7a97 created=2026-09-28T20:00:54+00:00 phase=1 -->
### aaa7162b7a97 · discovery · Shape for phase 2/3: where the visual vocabulary now lives (phase 1)

`fr.acceptance.model.Visual` (states/interactions StrictStr tuples, `check_visual_names` the shared non-empty/no-duplicate validator) and `Row.visual: Visual | None`. `fr.record.model.VisualShot` (path, shows — min_length=1), `VisualEvidence` (row, optional script, shots — min_length=1), `StepRecord.visual: tuple[VisualEvidence, ...]` in the `evidence` section group (`_SECTION_FIELDS["evidence"]` now: `evidence`, `emitted`, `visual`). Matrix kind is now version 3, record kind version 4 (`RECORD_SCHEMA_VERSION`). None of this phase touches `_VERIFIABLE_EVIDENCE`/`_DERIVED_EVIDENCE` in `run_cmd.py`, the `witness_transcript`/`read_file_since`/`shell_named_since` telemetry predicates (spec §C), the `fr-goal.yaml` manifest's `visual` evidence name, or the skills/agent prose (spec §E) — all still owed by a later phase.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-28T20:00:54+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

no separate refactor pass — Visual + check_visual_names were designed as the shared helper from the start (T2.S3's job), so T1 itself has nothing left to extract: one small closed model plus one field on Row.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-28T20:00:54+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

VisualShot/VisualEvidence mirror existing closed-model patterns (TickItem, AcceptanceItem) exactly; two small models with no shared logic between them to extract.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-09-28T20:00:54+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

matrix_visual.py/record_visual.py are built directly from matrix_verify.py/record_input_unconfirmed.py's own shape (the established pattern for a stamp-only hop); the one piece of duplication that did exist — the matrix guard — was extracted to guard_matrix (shared by both matrix hops) as part of writing T4.S2, not after.

<!-- fr:journal kind=finding scope=plan id=p1-f1 created=2026-09-28T20:04:39+00:00 phase=1 state=open review_scope=in -->
### p1-f1 · finding [open] (reviewer: in scope) · visual-evidence-row-flag left not-implemented although phase 1 implements and tests it (phase 1)

The phase links the row and its unit tests exercise the whole claim; acceptance-matrix rule requires moving it with levels in the same PR.

<!-- fr:journal kind=finding scope=plan id=p1-f2 created=2026-09-28T20:04:39+00:00 phase=1 state=open review_scope=in -->
### p1-f2 · finding [open] (reviewer: in scope) · P1.T4.S3 ticked without the pass count its text asks for (phase 1)

The step says to put the targeted run's pass count in the step note; note was null.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-09-28T20:04:39+00:00 phase=1 -->
### review-p1 · review · phase 1 code review: 2 findings (both in scope) (phase 1)

Independent reviewer (separate context, standard tier) read the phase-1 state against spec §A/§B/§G and the artifact-versioning rule.
Correct: Visual model + shared check_visual_names, Row.visual, acceptance add --visual-*, set-status preserving visual, AcceptanceItem.visual, VisualShot/VisualEvidence/StepRecord.visual in the evidence group, RECORD_SCHEMA_VERSION 4, matrix 2->3 and record 3->4 stamp-only migrations registered and imported, chain reachability asserted, reports in sync.
Findings: p1-f1 (row status), p1-f2 (missing step note). Method note: the reviewer had no shell and read files directly rather than the diff.

<!-- fr:journal kind=finding scope=plan id=p1-f1-resolved created=2026-09-28T20:04:39+00:00 phase=1 state=fixed resolves=p1-f1 -->
### p1-f1-resolved · finding [fixed] · resolves p1-f1: visual-evidence-row-flag left not-implemented although phase 1 implements and tests it (phase 1)

fr acceptance set-status visual-evidence-row-flag -> ci with unit levels test_acceptance_visual.py and test_record_visual.py (commit 2b242f36); reports regenerated.

<!-- fr:journal kind=finding scope=plan id=p1-f2-resolved created=2026-09-28T20:04:39+00:00 phase=1 state=fixed resolves=p1-f2 -->
### p1-f2-resolved · finding [fixed] · resolves p1-f2: P1.T4.S3 ticked without the pass count its text asks for (phase 1)

P1.T4.S3 note backfilled with the targeted and full-suite counts (commit 9aceb0a3).
