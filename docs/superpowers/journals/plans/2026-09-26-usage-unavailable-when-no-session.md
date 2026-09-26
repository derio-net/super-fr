# Journal: 2026-09-26-usage-unavailable-when-no-session

<!-- fr:journal kind=decision scope=plan id=one-phase-plan created=2026-09-26T15:06:48 -->
### one-phase-plan · decision · Single agentic standard-tier phase

Per operator: one phase, debugging-first (red tests, then fix, then refactor/gates and matrix/fragment bookkeeping).

<!-- fr:journal kind=decision scope=plan id=placeholder-after-merge created=2026-09-26T15:46:43 phase=1 -->
### placeholder-after-merge · decision · Placeholder written after the merge (phase 1)

capture() builds the no-session-found placeholder only when the merged list is empty, and _merge drops any earlier placeholder, so real sessions always win and repeated empty captures keep exactly one. Reason is kept verbatim in _KEPT_REASONS (NO_SESSION_FOUND).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-26T15:46:43 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

RED-only task: it adds failing tests and no production code, so there was nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-09-26T15:46:43 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

The change is a three-line filter in _merge plus one fallback after it; nothing duplicated to extract.
