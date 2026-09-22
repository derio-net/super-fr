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

<!-- fr:journal kind=discovery scope=plan id=34ea50f5a3db created=2026-09-22T13:54:20 phase=2 -->
### 34ea50f5a3db · discovery · P2.T1.S1 RED: arguments not scanned, vocabulary empty, no key-check helper (phase 2)

12 failures, each for the intended reason. test_every_spelling_of_the_isolation_flag_is_the_claude_code_argument[isolation: 'worktree'] (and the 4 other spellings) / test_a_bare_argument_is_a_violation_naming_its_harness[...] (4): AssertionError: assert [] == [Violation(...)] — scan_prose sees no arguments. test_argument_vocabulary_is_exactly_the_spec_table: every harness maps to {}. test_an_argument_inside_a_one_harness_clause_is_still_a_violation: assert [] == ['run_in_background']. test_the_import_time_key_check_names_the_mapping_it_rejects: ImportError: cannot import name 'require_every_harness' from 'fr.harness.prose'. The excused-in-clause and case/word-boundary tests pass vacuously at RED (nothing is scanned) and are meaningful only after GREEN.

<!-- fr:journal kind=discovery scope=plan id=p2-expected-red-phase3 created=2026-09-22T13:55:02 phase=2 -->
### p2-expected-red-phase3 · discovery · Expected red of phase 3: both neutrality tripwires, marked xfail(strict=True) (phase 2)

Populating ARGUMENT_VOCABULARY (P2.T1.S2) makes the scan flag exactly the prose phase 3 scopes: (1) agent tripwire — plugins/super-fr/agents/fr-phase-executor.md:121 run_in_background (Long-commands paragraph) plus its 4 .opencode/agent mirrors :116 [P3.T2.S1]; (2) skill tripwire — plugins/super-fr/skills/fr-goal/SKILL.md:59 isolation: "worktree" (§2 cross-repo dispatch, outside a clause) plus both mirrors [P3.T2.S2]. The orchestrator's dispatch anticipated only (1); (2) follows from the same vocabulary (spec 3.A removes the agent-only extra_tools, so the flag is now global). Both assertions carry pytest.mark.xfail(strict=True, reason=...) in tests/unit/test_tripwire_skill_tool_neutrality.py: phase 3 MUST remove both markers — strict makes a forgotten marker an XPASS failure.

<!-- fr:journal kind=discovery scope=plan id=p2-expected-red-phase3-dispatch-prose created=2026-09-22T13:55:59 phase=2 -->
### p2-expected-red-phase3-dispatch-prose · discovery · Expected red of phase 3 also covers two fr-goal whole-file scans in test_fr_goal_dispatch_prose.py (phase 2)

test_the_new_tool_mention_stayed_inside_the_scoped_clause and test_the_fallback_clause_still_names_no_harness_specific_tool_unscoped both assert scan_prose(fr-goal SKILL.md) == [] and now see fr-goal/SKILL.md:59 isolation: "worktree" (§2, P3.T2.S2). Both marked xfail(strict=True); phase 3 must remove these two markers along with the two in test_tripwire_skill_tool_neutrality.py (four markers total).
