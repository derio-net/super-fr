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

<!-- fr:journal kind=discovery scope=plan id=p3-t3-rules-scoped created=2026-09-22T14:28:13 phase=3 -->
### p3-t3-rules-scoped · discovery · P3.T3.S1: rules scoped; fr-plan-override and artifact-versioning had nothing to scope; stale fr-goal section numbers fixed (phase 3)

fr-plan-override.md and .claude/rules/artifact-versioning.md carried no violation (measured by the widened tripwire), so neither changed. Scoped: fr-isolation-required (canonical) — new **Harness — edit gate:** clause (Claude Code hook on Edit/Write/MultiEdit/NotebookEdit; OpenCode fr-opencode-plugin tool.execute.before on edit/write/patch/multiedit, bash ungated #436 — from packages/fr-opencode-plugin/src/index.ts EDIT_TOOLS; Hermes pre_tool_call on write_file|patch — from .hermes/config.snippet.yaml, parity row enforced), 'Agent tool'/'Bash tool' in Why reworded neutrally, carve-out's flag + guard hook + delegate_task folded into one **Harness — subagent worktree:** clause (the separate 'Enforcement, not prose' paragraph is gone). fr-worktree-override: the existing three-harness paragraph got a **Harness — native worktree commands:** lead-in. Hand-maintained .claude/rules/fr-isolation-required.md updated to match. While there: both rule files said 'fr-goal §6 dispatches phase executors' and '§3 keeps the flag' — fr-goal's dispatch is §5 and the cross-repo flag is §2, corrected. AGENTS.md was NOT touched (phase 4/5 owns its stale surfaces).

<!-- fr:journal kind=discovery scope=plan id=p3-t3-refactor-reread created=2026-09-22T14:31:18 phase=3 -->
### p3-t3-refactor-reread · discovery · P3.T3.S3 REFACTOR: every new Harness clause reread per reader; one arm tightened (phase 3)

Reread all six new clauses (executor long commands; fr-goal §2 cross-repo agents; rule edit gate; rule subagent worktree; worktree-override native worktree commands; repo-mirror edit gate + subagent worktree) as a Claude Code, an OpenCode and a Hermes reader. Each arm carries an action or a concrete fact its reader needs (a mechanism, an argument, or 'nothing to refuse — dispatch normally'), none only name-drops. One fix: the OpenCode arm of both edit-gate clauses said bash is ungated but not what to do about it — now 'a known gap, not a sanctioned bypass: make your edits with the edit tools' (wording AGENTS.md already uses). Also formatted tests/unit/test_fr_goal_dispatch_prose.py (a blank line lost with _PHASE_3_OWES).

<!-- fr:journal kind=finding scope=plan id=p3r-1 created=2026-09-22T14:40:04 phase=3 state=open -->
### p3r-1 · finding [open] · fr-goal §2's Claude Code arm is false: the flag gives a worktree of THIS repo, not the target (phase 3)

Review a44ffe50334af3c87, verified by the orchestrator: fr-worktree-create.sh:28 sends agent-* to mimic_default, which cuts the worktree under the toplevel of the CALLER's cwd. So on Claude Code isolation:worktree gives a cross-repo agent a detached worktree of the current repo; every harness's agent must enter isolation in the other repo itself, and fr isolation up defaults --repo to cwd (a delegated agent inherits the parent's). The same false premise is in spec §3.D (mine), the rule's pointer, and the guard hook's refusal message. Fix: harness-neutral unscoped instruction (fr isolation up --repo <path> --branch <b>, or fr run start from that repo), scoped clause states only the flag facts.

<!-- fr:journal kind=finding scope=plan id=p3r-2 created=2026-09-22T14:40:04 phase=3 state=open -->
### p3r-2 · finding [open] · Hermes edit-gate arm omits the terminal/execute_code gap the OpenCode arm discloses; lead sentence overclaims (phase 3)

Hermes hook header: terminal/execute_code are gated by fr-isolation-guard only (git/gh mutations, parity partial). Fix the prose (caveat + 'edit with write_file/patch'), soften 'every supported harness enforces this'. The parity.yaml declaration (Hermes enforced vs OpenCode partial for the same gap) is filed as a follow-up issue, not changed here.

<!-- fr:journal kind=finding scope=plan id=p3r-3 created=2026-09-22T14:40:04 phase=3 state=open -->
### p3r-3 · finding [open] · Stale §3/§6 in the shipped guard refusal message and hook/test comments (phase 3)

fr-phase-executor-guard.sh:65 reason string says fr-goal §3/§6 (now §2/§5) and repeats the p3r-1 false premise; also fr-isolation-guard.sh:141 comment, tests test_hooks_phase_executor_guard.py:123, test_hooks_guard.py:681.

<!-- fr:journal kind=finding scope=plan id=p3r-4 created=2026-09-22T14:40:05 phase=3 state=open -->
### p3r-4 · finding [open] · Long-commands test searches needles across the whole clause, not per arm (phase 3)

OpenCode's 'kill' satisfied by Hermes' process(kill); a wrong fact like 'On OpenCode pass background=true' passes. Fix: split on the **Claude Code**/**OpenCode**/**Hermes** leads; required AND forbidden needles per arm.

<!-- fr:journal kind=finding scope=plan id=p3r-m1 created=2026-09-22T14:40:05 phase=3 state=open -->
### p3r-m1 · finding [open] · OpenCode detach recipe drops the exit code and never says how to stop the job (phase 3)

Use (cmd; echo "exit=$?") > log 2>&1 & and kill the job before handback; matrix note must not call this arm 'verified' — it is sourced for timeout/kill, the detach survival is what the smoke checks.

<!-- fr:journal kind=finding scope=plan id=p3r-m2 created=2026-09-22T14:40:06 phase=3 state=refuted -->
### p3r-m2 · finding [refuted] · Row executor-long-commands-per-harness at ci while the smoke is owed (phase 3)

Partly refuted: the row's acceptance sentence is that the executor TELLS each harness's reader how to run a long command — prose, which the per-arm test pins at ci. The behaviour (not killed, nothing left running) is the Test Plan smoke's; the note is made explicit about that split rather than demoting a correctly pinned claim.

<!-- fr:journal kind=finding scope=plan id=p3r-m3m4 created=2026-09-22T14:40:06 phase=3 state=open -->
### p3r-m3m4 · finding [open] · Carve-out lead-in dangles into the scoped clause; 'this hook' singular; relative hook path (phase 3)

Move the Harness clause after the #420 bullets; 'the tool-layer backstops'; cite plugins/super-fr/hooks/hermes/fr-isolation-required.sh.

<!-- fr:journal kind=finding scope=plan id=p3r-1-resolved created=2026-09-22T14:43:08 state=fixed resolves=p3r-1 -->
### p3r-1-resolved · finding [fixed] · resolves p3r-1: fr-goal §2's Claude Code arm is false: the flag gives a worktree of THIS repo, not the target

fr-goal §2 now tells EVERY cross-repo agent to enter isolation in its own repo (fr isolation up --repo <path> --branch <b>); the scoped clause says the Claude Code flag only cuts a worktree of THIS repo. Same premise corrected in the rule (canonical + hand mirror), the guard's refusal message, the spec §3.D (marked corrected), and two test docstrings. Pinned: tests/unit/test_fr_goal_cross_repo_prose.py (red first).

<!-- fr:journal kind=finding scope=plan id=p3r-2-resolved created=2026-09-22T14:43:08 state=fixed resolves=p3r-2 -->
### p3r-2-resolved · finding [fixed] · resolves p3r-2: Hermes edit-gate arm omits the terminal/execute_code gap the OpenCode arm discloses; lead sentence overclaims

Hermes edit-gate arm now states the terminal/execute_code gap and says edit with write_file/patch; lead sentence softened ('gates its edit tools'; shell writes are the gap on every harness); hand mirror too. Declaration inconsistency filed as #561.

<!-- fr:journal kind=finding scope=plan id=p3r-3-resolved created=2026-09-22T14:43:09 state=fixed resolves=p3r-3 -->
### p3r-3-resolved · finding [fixed] · resolves p3r-3: Stale §3/§6 in the shipped guard refusal message and hook/test comments

fr-phase-executor-guard.sh refusal now cites §5/§2 and states the flag's real effect; fr-isolation-guard.sh comment and three test docstrings §3/§6 -> §2/§5. test_the_guard_refusal_cites_the_current_sections_and_no_false_premise (red first).

<!-- fr:journal kind=finding scope=plan id=p3r-4-resolved created=2026-09-22T14:43:09 state=fixed resolves=p3r-4 -->
### p3r-4-resolved · finding [fixed] · resolves p3r-4: Long-commands test searches needles across the whole clause, not per arm

test_long_commands_tell_each_harness_what_to_do splits the clause per 'On **Harness**' lead (whitespace-tolerant) with required AND forbidden needles per arm.

<!-- fr:journal kind=finding scope=plan id=p3r-m1-resolved created=2026-09-22T14:43:10 state=fixed resolves=p3r-m1 -->
### p3r-m1-resolved · finding [fixed] · resolves p3r-m1: OpenCode detach recipe drops the exit code and never says how to stop the job

OpenCode detach recipe keeps the exit code ((cmd; echo "exit=$?") > log 2>&1 & echo $! > log.pid) and stops it with kill "$(cat log.pid)" (each bash call is a fresh shell, $! does not survive); required by the per-arm test. Matrix note states this arm is the one not verified from source.

<!-- fr:journal kind=finding scope=plan id=p3r-m3m4-resolved created=2026-09-22T14:43:10 state=fixed resolves=p3r-m3m4 -->
### p3r-m3m4-resolved · finding [fixed] · resolves p3r-m3m4: Carve-out lead-in dangles into the scoped clause; 'this hook' singular; relative hook path

Subagent-worktree clause moved after the #420 bullets; 'These hooks are the tool-layer backstop'; Hermes hook cited by its repo path.

<!-- fr:journal kind=review scope=plan id=p3-review created=2026-09-22T14:43:10 phase=3 -->
### p3-review · review · Phase 3 review — separate reviewer, fixes applied (phase 3)

Reviewer: separately dispatched general-purpose subagent (a44ffe50334af3c87), adversarial on prose accuracy, every harness claim traced to a repo file. Verdict: with fixes. I1 (p3r-1) verified by the orchestrator against fr-worktree-create.sh:28 — the Claude Code flag yields a worktree of the CURRENT repo; a long-standing false premise in fr-goal §2, the rule, the guard message and this plan's own spec, all corrected. p3r-2..4, m1, m3/m4 fixed test-first where testable; m2 refuted (ci pins the prose the row claims; behaviour is the smoke's). Parity declaration split out as #561.

<!-- fr:journal kind=discovery scope=plan id=p4-t1-red created=2026-09-22T14:51:29 phase=4 -->
### p4-t1-red · discovery · P4.T1.S1 RED: the sentence-level predicate accepts all four ungoverned negations (phase 4)

Added test_a_negation_that_does_not_govern_the_phrase_does_not_count (4 params, the adversarial review's four verbatim) and test_a_governing_negation_counts (shipped description + pre-#532 'Dispatch it WITHOUT `isolation: "worktree"`.'). Against the current _rules_out_a_second_worktree (phrase AND any not/never/without anywhere in the sentence): 4 failed, 13 passed — each must-fail case returned True (AssertionError: the negation here does not govern the second-worktree phrase). Case 2 is caught only because the sentence split is on [.;] and not on the em dash; case 3 ('Do not hesitate to pass isolation: "worktree"') additionally defeats spec 3.E's literal 'negation within six words before' rule — 'not' precedes the flag by 3 words — so a window alone is insufficient.

<!-- fr:journal kind=discovery scope=plan id=p4-t1-rule created=2026-09-22T14:53:00 phase=4 -->
### p4-t1-rule · discovery · P4.T1.S2/S3: negation must GOVERN the phrase — filler-only gap, stricter than spec 3.E's window; one flag regex (phase 4)

Rule: clause split on . ; —; phrase = \bsecond\s+worktree\b or ARGUMENT_VOCABULARY['claude-code']['isolation: "worktree"']; walking back from the phrase, every word must be filler (into|in|a|an|the|any|pass|passing|use|using|with), at most 6, until a negation (never|without|not|no). Spec 3.E's plain six-word window passes 'Do not hesitate to pass isolation: "worktree"' (not negates hesitate), so spec 3.E was amended in this phase. pass/use added to the orchestrator's suggested filler so 'Do not pass `isolation: "worktree"`' (a natural prohibition) passes; 'to' stays non-filler, which is what fails the hesitate case. Extra must-pass params: do-not-pass-the-flag, no-second-worktree. REFACTOR: the module's local isolation regex AND the negative scan's _FLAG now both reuse the vocabulary pattern (one definition); consequence: _FLAG is now case-sensitive and also matches =/JSON/backtick spellings. Row phase-executor-description-rules-out-second-worktree: not-implemented -> ci.

<!-- fr:journal kind=finding scope=plan id=p4r-1 created=2026-09-22T14:56:25 phase=4 state=fixed -->
### p4r-1 · finding [fixed] · Double negation accepted: 'It cannot run without a second worktree' passed (phase 4)

Review a0eb0f895fbd2695f. Fixed: _FLIPPERS (negations + nothing/fail(s|ing)/only) earlier in the clause flip the governing negation. Five must-fail cases added (red first).

<!-- fr:journal kind=finding scope=plan id=p4r-2 created=2026-09-22T14:56:25 phase=4 state=fixed -->
### p4r-2 · finding [fixed] · Natural prohibitions rejected ('Never dispatch it into…', contractions); failure message silent on the accepted shape (phase 4)

Found by the orchestrator's own probe ('It never runs in a second worktree') and the review. Fixed: filler gains it/dispatch*/run(s)/be/given/give/get/create/need(s) (to/hesitate stay out); negations gain cannot and common contractions; assert message states the shape with an example. Eight must-pass cases added (red first).

<!-- fr:journal kind=finding scope=plan id=p4r-3 created=2026-09-22T14:56:25 phase=4 state=refuted -->
### p4r-3 · finding [refuted] · Clause split misses ?/!/: (phase 4)

Refuted for this PR: the reviewer's own '?' case ('No second worktree? Then create one.') cannot be caught by splitting — 'No second worktree' alone IS a prohibition — and the ':'/',' cases need contrived text. No realistic description is mis-judged; adding separators without a failing realistic case is speculative.

<!-- fr:journal kind=finding scope=plan id=p4r-4 created=2026-09-22T14:56:26 phase=4 state=refuted -->
### p4r-4 · finding [refuted] · _FLAG scan lost case-insensitivity (phase 4)

Refuted per the review's own evidence: every scanned tree's flag occurrences are lowercase and the flag is a case-sensitive key/value in the dispatch arguments, so 'Isolation: "Worktree"' would not trigger the harmful dispatch.

<!-- fr:journal kind=review scope=plan id=p4-review created=2026-09-22T14:56:26 phase=4 -->
### p4-review · review · Phase 4 review — separate reviewer, fixes applied (phase 4)

Reviewer a0eb0f895fbd2695f probed ~50 sentences in both directions. p4r-1 (double negation, false positive) and p4r-2 (natural prohibitions + contractions, false negatives; message) fixed test-first; p4r-3/p4r-4 refuted with reasoning; row level ref confirmed correct (p4r-5). Stated plainly: this predicate parses English with word lists, and three review rounds have each found new sentence shapes — the structural alternative (pin an exact canonical sentence) is put to the operator rather than decided here, since q3 chose this approach.
