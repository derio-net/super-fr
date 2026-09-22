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

<!-- fr:journal kind=finding scope=plan id=p1r-m1 created=2026-09-22T13:52:34 phase=2 state=open -->
### p1r-m1 · finding [open] · Vocabulary test docstring claims emptiness it does not assert; in-function import now unnecessary (phase 2)

Phase-1 review minors 1+3, filed against phase 2 (which rewrites this test): tests/unit/test_harness_vocabulary.py:223 docstring says values are empty until phase 2 but asserts keys only; the import at :221 can move top-level now the name exists. Fix when phase 2 populates the vocabulary: correct the docstring and hoist the import.

<!-- fr:journal kind=finding scope=plan id=p1r-m2 created=2026-09-22T13:52:34 phase=2 state=open -->
### p1r-m2 · finding [open] · Closed-world guard for both vocabularies; prose.py error message names the wrong vocabulary (phase 2)

Phase-1 review minor 2, filed against phase 2 (which makes prose.py consume ARGUMENT_VOCABULARY): extend the two-harness uniqueness test across BOTH vocabularies (spec 3.A); consider an import-time key check for ARGUMENT_VOCABULARY in prose.py; fix prose.py:54-58, whose error message names TOOL_VOCABULARY while checking _HARNESS_LABELS.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-09-22T13:52:35 phase=1 -->
### p1-review · review · Phase 1 review — separate reviewer, ready to proceed (phase 1)

Reviewer: separately dispatched general-purpose subagent (a736b1a0f4178ac86), superpowers:requesting-code-review template, range f1fcd157..HEAD. Verdict: ready; no critical/important. Scope exact (nothing from phase 2 pulled forward), type fits phase 2, red recorded (d788290847d4), executor did not touch the run cursor; reviewer re-ran tests/ruff/mypy green. Three minors received and verified: all concern code phase 2 rewrites, so filed against phase 2 as open findings p1r-m1, p1r-m2 (they gate phase 2's review), not fixed twice.
