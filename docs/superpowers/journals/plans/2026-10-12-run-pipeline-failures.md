# Journal: 2026-10-12-run-pipeline-failures

<!-- fr:journal kind=discovery scope=plan id=p1-render-only-param created=2026-10-11T22:40:36+00:00 phase=1 -->
### p1-render-only-param · discovery · render_committed_set takes only= (phase 1)

P1.T3.S2 done: render_committed_set(matrix, root, only=...) filters at the source, so every caller passes tracked_reports(root) rather than filtering its output. The implementation was written before the tests this phase (not strict red-first); the tests were then verified red by stashing the source changes (2 of 9 unit, 6 of 6 integration failed) and green with them.
