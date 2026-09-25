# Journal: 2026-09-25-triage-batches

<!-- fr:journal kind=discovery scope=plan id=905f9846fce9 created=2026-09-25T20:38:46 phase=1 -->
### 905f9846fce9 · discovery · no-refactor-because P1.T1 (phase 1)

Red-only task: it writes failing tests and changes no production code, so there is nothing to refactor; the green task follows.

<!-- fr:journal kind=discovery scope=plan id=eb2d1827ddaf created=2026-09-25T20:38:48 phase=1 -->
### eb2d1827ddaf · discovery · no-refactor-because P1.T2 (phase 1)

Glue only (a schema literal, a list verb, a stub package and CI wiring); P1.T3 verifies it end to end and records a cleanup if one is needed.

<!-- fr:journal kind=discovery scope=plan id=d54428244b78 created=2026-09-25T20:38:51 phase=2 -->
### d54428244b78 · discovery · no-refactor-because P2.T6 (phase 2)

This task IS the phase's refactor and quality gate; a refactor step of a refactor step would be circular.

<!-- fr:journal kind=discovery scope=plan id=d92d3b3c2ec6 created=2026-09-25T20:38:52 phase=3 -->
### d92d3b3c2ec6 · discovery · no-refactor-because P3.T5 (phase 3)

Docs, skill prose, mirrors and the version bump: no production code is written, so there is nothing to refactor; the mirror and bump --check gates in P3.T6 cover correctness.

<!-- fr:journal kind=discovery scope=plan id=3cc7e3015849 created=2026-09-25T20:38:54 phase=3 -->
### 3cc7e3015849 · discovery · no-refactor-because P3.T6 (phase 3)

This task IS the phase's refactor and quality gate; a refactor step of a refactor step would be circular.

<!-- fr:journal kind=decision scope=plan id=model-override-opus-5-5 created=2026-09-25T22:44:49 -->
### model-override-opus-5-5 · decision · Operator: Opus 5.5 on every tier for this run

Operator (2026-09-25): run implementation with Opus 5.5 on every tier. Standing bindings (claude-code: mechanical=haiku-4.5, standard=sonnet-5, hard=opus-5.5) are left untouched; each dispatch passes Opus 5.5 explicitly and records it with fr run claim --model claude-opus-5-5.
