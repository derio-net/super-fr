# Journal: 2026-10-04-arch-stage-dump

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-10-04T04:39:59+00:00 -->
### repro-1 · repro · Snapshot tabs dump every batch stage

Architecture page 'Snapshot timeline': every snapshot tab renders one <span><code>batch</code> stage</span> per batch in Snapshot.batches inside div.stages, no heading or grouping (82 pairs on this repo, repeated per tab). Repro: _snapshot_panel(snap, None) with many batches.

<!-- fr:journal kind=root-cause scope=debug id=rc-1 created=2026-10-04T04:40:00+00:00 -->
### rc-1 · root-cause · _snapshot_panel prints the raw batches mapping

packages/fr/src/fr/triage/architecture.py _snapshot_panel (~L372-378) joins a span per (batch, stage) sorted by batch name: it prints the raw Snapshot.batches mapping instead of aggregating it. Renderer-only; Snapshot data and diff_snapshots are correct (Batch stage changes list is fine).

<!-- fr:journal kind=finding scope=debug id=fix-1 created=2026-10-04T04:51:41+00:00 state=fixed -->
### fix-1 · finding [fixed] · Stage counts replace the per-batch wall

New _stage_counts renders one chip per stage (BATCH_STAGES lifecycle order, stages unknown to the current vocabulary sorted last) and folds the per-batch list into a closed <details class=stages>. Pinned by tests/unit/test_triage_architecture.py::test_a_snapshot_tab_counts_batches_per_stage_and_folds_the_list (red before the fix) and ::test_a_snapshot_with_no_batches_says_so.

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-10-04T04:51:56+00:00 -->
### review-1 · review · Self-review of the diff: no findings

Reviewed the merge-base diff (4 files). Checked: stage and batch names HTML-escaped; details closed by default; chips reuse existing .chips/.chip CSS; empty snapshot still reads 'no batches'; mypy Literal-list inference fixed by annotating order: list[str]. No findings raised. Full suite 8095 passed / 105 skipped; ruff, format and mypy clean.
