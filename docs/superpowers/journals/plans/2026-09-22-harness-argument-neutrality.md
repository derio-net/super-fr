# Journal: 2026-09-22-harness-argument-neutrality

<!-- fr:journal kind=discovery scope=plan id=4ecbf673a96c created=2026-09-22T13:47:39 phase=3 -->
### 4ecbf673a96c · discovery · no-refactor-because P3.T2 (phase 3)

Declared at planning time, structural: P3.T2 edits prose only (agent clause, fr-goal §2) and its refactor is P3.T3.S3, which rereads every new Harness clause from this phase — T2's included — for each harness's reader. A separate T2 refactor step would repeat that read.

<!-- fr:journal kind=discovery scope=plan id=c9d2eb7cf1c1 created=2026-09-22T13:47:40 phase=5 -->
### c9d2eb7cf1c1 · discovery · no-refactor-because P5.T1 (phase 5)

Declared at planning time, structural: P5.T1 changes documentation text only (a matrix sentence via fr acceptance, two AGENTS.md passages); there is no code to refactor.

<!-- fr:journal kind=discovery scope=plan id=ab612304e428 created=2026-09-22T13:47:40 phase=5 -->
### ab612304e428 · discovery · no-refactor-because P5.T2 (phase 5)

Declared at planning time, structural: P5.T2 is a version bump plus verification runs; it writes no code.

<!-- fr:journal kind=discovery scope=plan id=d788290847d4 created=2026-09-22T13:48:56 phase=1 -->
### d788290847d4 · discovery · P1.T1.S1 RED: ARGUMENT_VOCABULARY missing (phase 1)

test_argument_vocabulary_is_keyed_by_exactly_the_harnesses failed with: ImportError: cannot import name 'ARGUMENT_VOCABULARY' from 'fr.harness' (packages/fr/src/fr/harness/__init__.py) — confirms the name does not exist yet, the correct RED reason before adding the empty closed-world mapping.
