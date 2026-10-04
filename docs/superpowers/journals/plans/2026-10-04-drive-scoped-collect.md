# Journal: 2026-10-04-drive-scoped-collect

<!-- fr:journal kind=decision scope=plan id=d-prev-facts-scope-check created=2026-10-04T06:23:07+00:00 phase=1 -->
### d-prev-facts-scope-check · decision · previous facts are scope-checked for batch_prs too (phase 1)

_previous_facts replaces _previous_batch_prs; known_batch_prs now also comes only from a same-scope facts.json (it always did live in the scope dir, so no practical change).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-04T06:23:07+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

acceptance rows, change fragment and verification only; no production code to clean
