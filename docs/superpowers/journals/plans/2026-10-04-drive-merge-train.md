# Journal: 2026-10-04-drive-merge-train

<!-- fr:journal kind=discovery scope=plan id=p1-visual-evidence-tests-fail-under-xdist created=2026-10-04T08:58:53+00:00 phase=1 -->
### p1-visual-evidence-tests-fail-under-xdist · discovery · tests/unit/test_run_evidence_visual.py (and a few timing tests) fail in the full -n auto suite but pass alone (phase 1)

The full suite on this host fails 4-7 tests (test_run_evidence_visual.py transcript-witness tests; once also test_records_commit stuck-lock, test_statusline_segment budget, test_sentinel_liveness) in two consecutive runs, yet all pass when run as those files alone (113 passed). They depend on harness transcripts/wall-clock and the host was loaded (suite took ~35 min). None touch the files this phase changed.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-10-04T08:58:53+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

train_line and summary_line were small additions beside existing helpers; nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-04T08:58:53+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

A two-line subclass and one raise site; nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-04T08:58:53+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

One loop printing train_line before the actions; nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t7 created=2026-10-04T08:58:53+00:00 phase=1 -->
### no-refactor-p1-t7 · discovery · no-refactor-because P1.T7 (phase 1)

A fragment file and acceptance rows; no code to clean.
