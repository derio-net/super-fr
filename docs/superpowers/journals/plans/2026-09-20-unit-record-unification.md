# Journal: 2026-09-20-unit-record-unification

<!-- fr:journal kind=discovery scope=plan id=nr-p1t3 created=2026-09-20T21:57:05 phase=1 -->
### nr-p1t3 · discovery · no-refactor-because P1.T3 (phase 1)

P1.T3 writes no production code. S1 CAPTURES real run cursors byte-for-byte as fixtures — refactoring a captured fixture would turn it into a constructed one, which is the exact thing the walking-skeleton rule forbids. S2 runs the full CI gate. Phase 1's authored code is refactored in P1.T2.S3.

<!-- fr:journal kind=discovery scope=plan id=nr-p7t2 created=2026-09-20T21:57:05 phase=7 -->
### nr-p7t2 · discovery · no-refactor-because P7.T2 (phase 7)

P7.T2 is acceptance status flips through fr acceptance set-status and a version bump through scripts/bump-version.py. Both produce files the repo documents as never hand-edited (the matrix, its three generated reports, nine version manifests, uv.lock). A refactor step over generated output is the hand-edit those rules exist to prevent.

<!-- fr:journal kind=discovery scope=plan id=nr-p7t3 created=2026-09-20T21:57:05 phase=7 -->
### nr-p7t3 · discovery · no-refactor-because P7.T3 (phase 7)

P7.T3 is the explainer and the final gate. The .html is produced by a renderer in another repo and carries a do-not-hand-edit banner; the .md's quality pass is inside S1 itself — the byte-for-byte re-render of the UNMODIFIED source that must pass before the real render, which is a stronger check than a refactor step. S2 is the CI gate.
