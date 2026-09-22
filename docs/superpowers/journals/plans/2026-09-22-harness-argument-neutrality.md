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

<!-- fr:journal kind=finding scope=plan id=p1r-m1-resolved created=2026-09-22T13:56:24 state=fixed resolves=p1r-m1 -->
### p1r-m1-resolved · finding [fixed] · resolves p1r-m1: Vocabulary test docstring claims emptiness it does not assert; in-function import now unnecessary

tests/unit/test_harness_vocabulary.py: ARGUMENT_VOCABULARY (and HarnessError, require_every_harness) imported at module top; test_argument_vocabulary_is_keyed_by_exactly_the_harnesses docstring now says it asserts keys only, and the values are pinned by the new test_argument_vocabulary_is_exactly_the_spec_table. Commit 'feat(fr): scan_prose flags harness-specific arguments'.

<!-- fr:journal kind=finding scope=plan id=p1r-m2-resolved created=2026-09-22T13:56:25 state=fixed resolves=p1r-m2 -->
### p1r-m2-resolved · finding [fixed] · resolves p1r-m2: Closed-world guard for both vocabularies; prose.py error message names the wrong vocabulary

Uniqueness: test_no_name_is_claimed_by_two_harnesses_across_both_vocabularies (tool+argument names per harness, pairwise, and no harness claims a name as both). Import-time check: prose.require_every_harness(name, mapping) runs for _HARNESS_LABELS, TOOL_VOCABULARY and ARGUMENT_VOCABULARY; its error names the mapping checked, replacing the inline check that blamed TOOL_VOCABULARY — pinned by test_the_import_time_key_check_names_the_mapping_it_rejects.

<!-- fr:journal kind=discovery scope=plan id=06f6c0af9ea2 created=2026-09-22T13:56:41 phase=2 -->
### 06f6c0af9ea2 · discovery · P2.T2.S1 RED: headings are scanned like body lines (phase 2)

test_a_heading_is_not_flagged[## Plan Skill Override] (and 3 other headings): AssertionError: assert [Violation(harness='claude-code', tool='Skill', line=1)] == []. test_the_same_word_in_a_body_line_is_still_flagged: the heading on line 1 is reported alongside the body mention on line 3. test_only_a_real_atx_heading_is_exempt passes at RED (nothing is exempt yet) and guards the GREEN regex.

<!-- fr:journal kind=discovery scope=plan id=11b2b72f9074 created=2026-09-22T13:57:35 phase=2 -->
### 11b2b72f9074 · discovery · P2.T3.S1 RED: scan_prose still accepts extra_tools (phase 2)

test_scan_prose_rejects_an_extra_tools_keyword: Failed: DID NOT RAISE <class 'TypeError'> — the parameter still exists. The three rewritten test_extra_tools_* tests (now test_the_isolation_flag_is_flagged_from_the_vocabulary_alone, ..._excused_by_a_scoped_clause_like_any_tool, test_scanning_does_not_mutate_either_vocabulary) pass already, since P2.T1 put the flag in the vocabulary; the agent tripwire calls scan_prose(text) with no extra and stays xfail on the executor's run_in_background.

<!-- fr:journal kind=finding scope=plan id=p2r-1 created=2026-09-22T14:13:13 phase=2 state=open -->
### p2r-1 · finding [open] · Strict xfails hide phase 3's RED and pass a PARTIAL fix silently (phase 2)

Review of phase 2 (a595be6374237b183): xfail(strict) only fails when EVERY violation is gone, so a canonical fixed but one mirror not re-synced, or a new unrelated violation, stays XFAIL; a bare xfail also swallows exceptions. My own instruction to the executor. Fix: each of the four assertions compares the violation set to the EXACT known list, so any change goes red; phase 3 flips each to empty.

<!-- fr:journal kind=finding scope=plan id=p2r-2 created=2026-09-22T14:13:13 phase=2 state=open -->
### p2r-2 · finding [open] · isolation pattern misses the JSON/dict key and backtick spellings (phase 2)

'"isolation": "worktree"', "'isolation': 'worktree'", 'isolation: `worktree`' pass unflagged; the dispatch tool's input IS {"isolation": "worktree"} (the repo's hook reads .tool_input.isolation). Spec-level gap. Fix: isolation["'`]?\s*[:=]\s*["'`]?worktree(?![\w-]) + spec 3.A amendment + parametrized cases.

<!-- fr:journal kind=finding scope=plan id=p2r-3 created=2026-09-22T14:13:13 phase=2 state=open -->
### p2r-3 · finding [open] · Hermes background pattern misses background=True and background: true; a test pinned the miss (phase 2)

Hermes is Python: terminal(cmd, background=True). test_argument_patterns_are_case_sensitive_and_word_bounded asserted it unflagged. Fix: \bbackground\s*[:=]\s*(?:true|True)\b, flip that assertion, amend spec 3.A.

<!-- fr:journal kind=finding scope=plan id=p2r-4 created=2026-09-22T14:13:14 phase=2 state=open -->
### p2r-4 · finding [open] · Heading skip also skips # comment lines inside fenced code (phase 2)

'```bash\n# run_in_background is needed\n```' is skipped though the docstring says only real ATX headings are. Fix: fence-aware skip (a heading is only a heading outside a fence).

<!-- fr:journal kind=finding scope=plan id=p2r-5 created=2026-09-22T14:13:14 phase=2 state=open -->
### p2r-5 · finding [open] · Heading lines still count toward a clause naming every harness (phase 2)

'**Harness — x:** Claude Code OpenCode\n## Hermes\nAgent' excuses Agent via a heading. Fix: heading lines neither name harnesses for a clause nor lead one.

<!-- fr:journal kind=finding scope=plan id=p2r-6 created=2026-09-22T14:13:15 phase=2 state=refuted -->
### p2r-6 · finding [refuted] · Plan note for P2.T2.S2 says the skill tripwire stays green (phase 2)

Refuted: plan step text records intent at planning time; the change (xfail, now the exact-set assertion) is recorded in the journal (p2-expected-red-phase3*) and this review, which is where the PR body is derived from. Rewriting a completed step's text would make the plan claim a history it did not have.

<!-- fr:journal kind=finding scope=plan id=p2r-7 created=2026-09-22T14:13:15 phase=2 state=open -->
### p2r-7 · finding [open] · isolation: "worktree-mode" is a false positive (phase 2)

\b before a hyphen; use (?![\w-]) like the tool-name convention.

<!-- fr:journal kind=finding scope=plan id=p2r-1-resolved created=2026-09-22T14:15:43 state=fixed resolves=p2r-1 -->
### p2r-1-resolved · finding [fixed] · resolves p2r-1: Strict xfails hide phase 3's RED and pass a PARTIAL fix silently

Four strict xfails replaced by exact-set assertions (_SKILLS_PHASE_3_OWES, _AGENTS_PHASE_3_OWES, _PHASE_3_OWES): any new, partial or changed violation now goes red; phase 3 empties them. No xfail marker remains.

<!-- fr:journal kind=finding scope=plan id=p2r-2-resolved created=2026-09-22T14:15:43 state=fixed resolves=p2r-2 -->
### p2r-2-resolved · finding [fixed] · resolves p2r-2: isolation pattern misses the JSON/dict key and backtick spellings

isolation pattern -> isolation["'`]?\s*[:=]\s*["'`]?worktree(?![\w-]); JSON key, dict key and backtick spellings added to the parametrized test (red first). Spec 3.A amended.

<!-- fr:journal kind=finding scope=plan id=p2r-3-resolved created=2026-09-22T14:15:44 state=fixed resolves=p2r-3 -->
### p2r-3-resolved · finding [fixed] · resolves p2r-3: Hermes background pattern misses background=True and background: true; a test pinned the miss

background pattern -> \bbackground\s*[:=]\s*(?:true|True)\b; background=True and background: true cases added (red first); the test that pinned background=True as prose now asserts it is flagged elsewhere and keeps only genuine negatives. Spec 3.A amended.

<!-- fr:journal kind=finding scope=plan id=p2r-4-resolved created=2026-09-22T14:15:44 state=fixed resolves=p2r-4 -->
### p2r-4-resolved · finding [fixed] · resolves p2r-4: Heading skip also skips # comment lines inside fenced code

_heading_lines is fence-aware: a # line inside ```/~~~ is scanned. test_a_hash_comment_inside_a_fenced_block_is_not_a_heading (red first) and test_a_real_heading_after_a_closed_fence_is_still_exempt.

<!-- fr:journal kind=finding scope=plan id=p2r-5-resolved created=2026-09-22T14:15:45 state=fixed resolves=p2r-5 -->
### p2r-5-resolved · finding [fixed] · resolves p2r-5: Heading lines still count toward a clause naming every harness

Heading lines neither lead a clause nor count toward naming a harness in _clause_is_valid. test_a_heading_cannot_name_a_harness_for_a_clause (red first).

<!-- fr:journal kind=finding scope=plan id=p2r-7-resolved created=2026-09-22T14:15:45 state=fixed resolves=p2r-7 -->
### p2r-7-resolved · finding [fixed] · resolves p2r-7: isolation: "worktree-mode" is a false positive

(?![\w-]) after worktree; isolation: "worktree-mode" asserted unflagged.

<!-- fr:journal kind=review scope=plan id=p2-review created=2026-09-22T14:22:57 phase=2 -->
### p2-review · review · Phase 2 review — separate reviewer, with fixes applied (phase 2)

Reviewer: separately dispatched general-purpose subagent (a595be6374237b183), requesting-code-review template, adversarial on scanner silence, range b0d58fda..ea6bf001. Verdict: ready with fixes. Received and verified: p2r-1 (strict xfails pass a partial fix silently — my own brief's design) fixed with exact-set assertions; p2r-2 (JSON/dict/backtick isolation spellings), p2r-3 (background=True / colon), p2r-4 (fenced # comments skipped as headings), p2r-5 (headings counted toward clause validity), p2r-7 (worktree-mode false positive) fixed test-first; p2r-6 refuted with reasoning. Spec 3.A amended. Full suite after fixes: 4392 passed, exit 0.

<!-- fr:journal kind=discovery scope=plan id=p3-t1-red-rules created=2026-09-22T14:24:19 phase=3 -->
### p3-t1-red-rules · discovery · P3.T1.S1 RED: the rules family carries 24 violations across 6 files (phase 3)

test_no_rule_names_a_harness_specific_tool_outside_a_scoped_clause fails (the 4 per-tree not-empty guards pass). Canonical plugins/super-fr/rules/fr-isolation-required.md: 8 MultiEdit, 9 NotebookEdit, 21 Agent, 140 isolation: "worktree", 159 Agent, 160 delegate_task; fr-worktree-override.md: 15 WorktreeCreate. Hand-maintained .claude/rules/fr-isolation-required.md: 5 MultiEdit, 6 NotebookEdit, 42 isolation: "worktree". Mirrors carry the same: .opencode/instructions/fr-isolation-required.md (8,9,21,140,159,160) + fr-worktree-override.md:15; .hermes/SOUL.d/super-fr-rules.md 10 MultiEdit, 11 NotebookEdit, 23 Agent, 142 isolation, 161 Agent, 162 delegate_task, 228 WorktreeCreate. fr-plan-override.md, artifact-versioning.md and the other repo-local rules are clean — nothing to scope there.
