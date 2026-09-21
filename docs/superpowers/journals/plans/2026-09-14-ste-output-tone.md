# Journal: 2026-09-14-ste-output-tone

<!-- fr:journal kind=decision scope=plan id=no-refactor-P3T1 created=2026-09-14T21:50:18 phase=3 -->
### no-refactor-P3T1 · decision · no-refactor-because: P3.T1 (phase 3)

no-refactor-because: P3.T1 adds one data file and one assertion; the identity test is already the single source of the check.

<!-- fr:journal kind=decision scope=plan id=no-refactor-P4T1 created=2026-09-14T21:50:36 phase=4 -->
### no-refactor-P4T1 · decision · no-refactor-because: P4.T1 (phase 4)

no-refactor-because: P4.T1 is a one-line text change in the agent definition plus one assertion.

<!-- fr:journal kind=decision scope=plan id=no-refactor-P4T2 created=2026-09-14T21:51:03 phase=4 -->
### no-refactor-P4T2 · decision · no-refactor-because: P4.T2 (phase 4)

no-refactor-because: P4.T2 is a generated version bump and matrix data edits; no code changes.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-09-14T22:27:47 phase=1 -->
### review-p1 · review · Phase 1 review: no findings (phase 1)

Reviewed 915942a against plan P1 and spec §5.B/§5.E.1. Style frontmatter, marker pair and test match the plan text exactly. The 80 skips in the gate run are pre-existing per-skill parametrised cases, not caused by output-styles/. Reviewed inline, not via requesting-code-review: 46 lines copied verbatim from the reviewed plan.

<!-- fr:journal kind=discovery scope=plan id=upstream-is-main created=2026-09-14T22:28:00 phase=1 -->
### upstream-is-main · discovery · Branch upstream is origin/main (phase 1)

fr isolation up set feat/ste-output-tone to track origin/main. A bare git push targets main. Always push with: git push -u origin feat/ste-output-tone.

<!-- fr:journal kind=discovery scope=plan id=173c595e7078 created=2026-09-14T22:36:06 phase=2 -->
### 173c595e7078 · discovery · no-refactor-because: P2.T1.S3 (phase 2)

Read the full shared STE block as a reader. Every sentence is 25 words or fewer (longest: 23 words, the Scope section's second sentence), uses active voice, and has no filler outside quoted examples. No sentence needed a change. Verified mechanically with a one-off word-count script (paragraphs joined across wrapped lines, bullets split on periods outside quotes).

<!-- fr:journal kind=finding scope=plan id=r2-m5-progressive created=2026-09-14T22:45:18 phase=2 state=refuted -->
### r2-m5-progressive · finding [refuted] · M5 progressive tense excluded: refuted (phase 2)

Reviewer suggested allowing the present progressive for work in progress. Refuted: ASD-STE100 excludes the progressive, and the operator asked for the standard. 'The test runs in the background' is a valid STE status line.

<!-- fr:journal kind=finding scope=plan id=r2-m8-loader created=2026-09-14T22:45:21 phase=2 state=refuted -->
### r2-m8-loader · finding [refuted] · M8 marker comments in style body: no action (phase 2)

Reviewer confirmed the frontmatter shape is valid and the ste-shared HTML comments reach the system prompt as a few literal tokens with no harm. No change needed.

<!-- fr:journal kind=finding scope=plan id=r2-i1-one-block created=2026-09-14T22:45:23 phase=2 state=refuted -->
### r2-i1-one-block · finding [refuted] · I1 optional 'one Insight block per reply': not adopted (phase 2)

Reviewer offered an optional rule limiting Insight blocks to one per reply. Not adopted: operator decision d3 is to keep the Insight blocks. The fix cancels only the length permission.

<!-- fr:journal kind=finding scope=plan id=r2-i1-insight created=2026-09-14T22:46:49 phase=2 state=fixed -->
### r2-i1-insight · finding [fixed] · I1 Insight override cancelled a limit that did not exist (phase 2)

Old text: 'does not permit replies longer than these rules permit' — the rules set no reply-length limit. Fix: name the hook's permission ('exceed typical length constraints'), state 'Insight blocks do not make a reply longer', and 'These rules take precedence over that prompt'. Test pins all three phrases.

<!-- fr:journal kind=finding scope=plan id=r2-i2-scope created=2026-09-14T22:46:51 phase=2 state=fixed -->
### r2-i2-scope · finding [fixed] · I2 Scope wider than d1 (phase 2)

Old: 'all text that you write for a person' covered code comments, docs, specs, CLI strings; conflicts with explainers-currency voice. Fix: closed list (replies, status updates, skill announcements, PR bodies, journal entries, subagent results) plus 'Do not apply them to files that you edit: code, comments, docs, specs, plans, or CLI and hook messages.' Spec §5.A updated. Test pins the exclusion.

<!-- fr:journal kind=finding scope=plan id=r2-i3-formats created=2026-09-14T22:46:54 phase=2 state=fixed -->
### r2-i3-formats · finding [fixed] · I3 No precedence for prescribed formats (phase 2)

Skills prescribe announcements and verbatim blocks; callers prescribe report layouts. Fix: 'If the operator, a skill or a caller gives a format or exact words, use them. Write your own sentences in STE.' Spec §5.A updated. Test pins it.

<!-- fr:journal kind=finding scope=plan id=r2-i4-length created=2026-09-14T22:46:57 phase=2 state=fixed -->
### r2-i4-length · finding [fixed] · I4 Text broke its own 20-word instruction limit; guard was prose (phase 2)

The Scope instruction had 23 words; journal 173c595e7078 wrongly checked it against the 25-word description limit and recorded 'no change needed' — that entry is superseded by this one. Fix: sentence rewritten (longest shared sentence now 19 words, checked by reader). Added test_no_shared_sentence_exceeds_the_description_limit (25-word guard in code) and test_sentence_splitter_finds_a_long_sentence (the guard can fail). The 20-word instruction limit stays a reader check: a test cannot tell instructions from descriptions (spec §5.E.7).

<!-- fr:journal kind=finding scope=plan id=r2-m1-filler-failopen created=2026-09-14T22:47:01 phase=2 state=fixed -->
### r2-m1-filler-failopen · finding [fixed] · M1 Filler test failed open on unbalanced quotes and line wraps (phase 2)

Fix: normalize whitespace; assert balanced double quotes.

<!-- fr:journal kind=finding scope=plan id=r2-m2-filler-list created=2026-09-14T22:47:04 phase=2 state=fixed -->
### r2-m2-filler-list · finding [fixed] · M2 FILLER tuple duplicated the Words list (phase 2)

Fix: the test parses the filler list from the Words bullet and asserts it contains just/really/i think.

<!-- fr:journal kind=finding scope=plan id=r2-m3-markers-headings created=2026-09-14T22:47:06 phase=2 state=fixed -->
### r2-m3-markers-headings · finding [fixed] · M3 Marker order unchecked; headings matched as substrings (phase 2)

Fix: _shared_block asserts START precedes END; section headings match as exact lines (re.M). _section normalizes whitespace so wrapped phrases match.

<!-- fr:journal kind=finding scope=plan id=r2-m4-instruction-two-meanings created=2026-09-14T22:47:08 phase=2 state=fixed -->
### r2-m4-instruction-two-meanings · finding [fixed] · M4 'instruction' used with two meanings (phase 2)

Fix: the Insight section says 'another prompt'; 'instruction' now only means a sentence type.

<!-- fr:journal kind=finding scope=plan id=r2-m6-code-spans created=2026-09-14T22:47:11 phase=2 state=fixed -->
### r2-m6-code-spans · finding [fixed] · M6 Commands counted toward the word limit (phase 2)

Fix: 'Put commands and paths in code spans. Do not count them as words.' The sentence splitter drops code spans.

<!-- fr:journal kind=finding scope=plan id=r2-m7-licence-wording created=2026-09-14T22:47:13 phase=2 state=fixed -->
### r2-m7-licence-wording · finding [fixed] · M7 One sentence close to ASD rule wording (phase 2)

Fix: 'Write one instruction in each sentence' reworded to 'Give only one instruction in a sentence.'

<!-- fr:journal kind=discovery scope=plan id=d113930ed739 created=2026-09-14T22:51:49 phase=3 -->
### d113930ed739 · discovery · Parametrized filler/length tests over STYLE and RULE (phase 3)

During P3.T1.S3 refactor, parametrized test_shared_text_uses_no_filler_outside_quoted_examples and test_no_shared_sentence_exceeds_the_description_limit over (STYLE, RULE) since the rule's shared block is identical to the style's. Moved RULE's definition next to STYLE at the top of the file. 10 tests pass (8 base + 2 new parametrize cases). Small, no separate commit needed.

<!-- fr:journal kind=discovery scope=plan id=cf0f14f90a5b created=2026-09-14T22:57:32 phase=3 -->
### cf0f14f90a5b · discovery · test_install_sh.py lives under tests/integration/, not tests/unit/ (phase 3)

P3.T2.S3 names tests/unit/test_install_sh.py; the file is actually tests/integration/test_install_sh.py (tests/unit/test_hermes_install_cmd.py is correct). Ran the integration path instead: uv run pytest tests/integration/test_install_sh.py tests/unit/test_hermes_install_cmd.py -q --no-cov -> 43 passed.

<!-- fr:journal kind=finding scope=plan id=r3-i1-opencode-consumers created=2026-09-14T23:07:13 phase=3 state=fixed -->
### r3-i1-opencode-consumers · finding [fixed] · I1 OpenCode instructions never reach consumer machines (phase 3)

Verified: scripts/install.sh (lines 535-558) copies OpenCode skills and commands only; no installer delivers .opencode/instructions, so the rule loads in OpenCode only inside this repo (opencode.json). Pre-existing gap, affects every shipped rule. Fixed by narrowing the claim: spec §2, §3 and the §8 row now say OpenCode gets the rule only inside this repo; phase 4 narrows the matrix row text before any status flip. Consumer delivery is listed as a follow-up in the PR body.

<!-- fr:journal kind=finding scope=plan id=r3-m2-token-cost created=2026-09-14T23:07:17 phase=3 state=fixed -->
### r3-m2-token-cost · finding [fixed] · M2 Token cost understated (phase 3)

Main thread loads both carriers (style ~400 words + rule ~460 words), ~1,100 input tokens, not 600. Spec §6 corrected.

<!-- fr:journal kind=finding scope=plan id=r3-m3-rule-header-paths created=2026-09-14T23:07:21 phase=3 state=fixed -->
### r3-m3-rule-header-paths · finding [fixed] · M3 Rule header named repo paths in every session (phase 3)

The globally installed rule header named plugins/ and docs/superpowers/ paths that do not exist in consumer repos. Header cut to: plugin also sends this text as an output style; output styles do not reach subagents or other harnesses; licence note.

<!-- fr:journal kind=finding scope=plan id=r3-m4-commit-messages created=2026-09-14T23:07:24 phase=3 state=fixed -->
### r3-m4-commit-messages · finding [fixed] · M4 Commit messages neither in nor out of scope (phase 3)

Added 'Do not apply them to commit messages.' to both carriers (consistent with d1 and spec-review R1), spec §5.A updated. TDD: scope test asserted it first (1 failed, 9 passed), then green.

<!-- fr:journal kind=finding scope=plan id=r3-m5-identity-strip created=2026-09-14T23:07:27 phase=3 state=fixed -->
### r3-m5-identity-strip · finding [fixed] · M5 Identity test compared stripped blocks (phase 3)

Added _raw_block: the identity test compares the unstripped bytes between the markers, after the marker count/order checks.

<!-- fr:journal kind=decision scope=plan id=r3-m6-hermes-row-text created=2026-09-14T23:07:30 phase=3 -->
### r3-m6-hermes-row-text · decision · M6 hermes-rules-soul-block row says three shipped rules (phase 3)

Pre-existing matrix text drift (five shipped rules now). Deferred to P4.T2.S2, which edits matrix.yaml anyway.

<!-- fr:journal kind=finding scope=plan id=r3-m6-uninstall-gap created=2026-09-14T23:07:33 phase=3 state=refuted -->
### r3-m6-uninstall-gap · finding [refuted] · M6 --uninstall misses fr-isolation-required and no-claude-p-batch (phase 3)

Pre-existing, tracked as open finding a3228f0cb118 in plan 2026-09-04-worktree-traceability. Out of scope here; this plan's own rule has its uninstall line.

<!-- fr:journal kind=decision scope=plan id=r3-m6-hermes-row-text-done created=2026-09-14T23:21:01 phase=4 -->
### r3-m6-hermes-row-text-done · decision · r3-m6 closed: hermes-rules-soul-block lists five rules (phase 4)

Deferred r3-m6 item done in P4.T2.S2 (aec12da): the row text now names five shipped rules, matching SHIPPED_RULES in test_tripwire_hermes_rules_sync.py. Confirmed by the phase 4 review.

<!-- fr:journal kind=finding scope=plan id=r4-m8-issue created=2026-09-14T23:21:03 phase=4 state=refuted -->
### r4-m8-issue · finding [refuted] · M8 File a GitHub issue for OpenCode consumer delivery: not done here (phase 4)

Filing an issue is an outward action the operator did not ask for. The follow-up is listed in the PR body (and in the matrix note); the operator can file it.

<!-- fr:journal kind=finding scope=plan id=r4-m1-executor-harness-claim created=2026-09-14T23:22:33 phase=4 state=fixed -->
### r4-m1-executor-harness-claim · finding [fixed] · M1 Spec §5.D claimed the executor line covers other harnesses (phase 4)

The agent file exists only in Claude Code; Hermes delegate_task loads fr-execute. Spec §5.D now says the line restates the rule in the executor's return contract, and names a pointer in fr-execute as the Hermes follow-up.

<!-- fr:journal kind=finding scope=plan id=r4-m2-spec-wording created=2026-09-14T23:22:36 phase=4 state=fixed -->
### r4-m2-spec-wording · finding [fixed] · M2 Spec §5.D wording lagged the implementation (phase 4)

Spec §5.D now says 'the result and every journal entry', matching fr-phase-executor.md.

<!-- fr:journal kind=finding scope=plan id=r4-m3-spec-row-table created=2026-09-14T23:22:39 phase=4 state=fixed -->
### r4-m3-spec-row-table · finding [fixed] · M3 Spec §8 table drifted from the matrix rows (phase 4)

Row wording aligned to matrix.yaml; levels for the two skipped rows now read 'unit (text) + operator walk'.

<!-- fr:journal kind=finding scope=plan id=r4-m4-skipped-notes created=2026-09-14T23:22:41 phase=4 state=fixed -->
### r4-m4-skipped-notes · finding [fixed] · M4 Skipped-row notes lost the Test Plan step numbers (phase 4)

ste-style-forced-in-claude-code notes cite Test Plan steps 1-4; ste-insight-blocks-kept-short cites step 4. Reports regenerated; fr acceptance report --check in sync.

<!-- fr:journal kind=finding scope=plan id=r4-m5-hermes-install-evidence created=2026-09-14T23:22:43 phase=4 state=fixed -->
### r4-m5-hermes-install-evidence · finding [fixed] · M5 ci row had no Hermes install-level evidence (phase 4)

Added super-fr:tests/unit/test_hermes_install_cmd.py (applies the SOUL.md block) to ste-rule-reaches-every-harness levels.

<!-- fr:journal kind=finding scope=plan id=r4-m6-long-line created=2026-09-14T23:22:45 phase=4 state=fixed -->
### r4-m6-long-line · finding [fixed] · M6 168-character line in fr-phase-executor.md (phase 4)

Wrapped to match the file's ~85-character lines.

<!-- fr:journal kind=finding scope=plan id=r4-m7-executor-test created=2026-09-14T23:22:48 phase=4 state=fixed -->
### r4-m7-executor-test · finding [fixed] · M7 Executor test raised IndexError on a renamed heading (phase 4)

Test asserts the return heading exists first, normalizes whitespace, and also pins 'every journal entry'.

<!-- fr:journal kind=finding scope=plan id=rebase-workflow-check-hermetic created=2026-09-15T19:12:54 state=fixed -->
### rebase-workflow-check-hermetic · finding [fixed] · test_cli_all_fails_when_nothing_is_discoverable was not hermetic

Found in the deliver gate and again after the rebase on 9ac7679. shipped_workflow_dirs always appends the marketplace clone under HOME, so on a machine with super-fr installed the test finds fr-goal and fails; CI has no clone and passed. Fix: the test sets HOME to an empty temp directory. Product code unchanged.

<!-- fr:journal kind=finding scope=plan id=r5-i1-version-clash created=2026-09-15T20:52:08 phase=5 state=fixed -->
### r5-i1-version-clash · finding [fixed] · I1 Branch version 4.4.0 clashes with released main (phase 5)

Verified: origin/main 9bb2248 is 4.4.0, released as v4.4.0 by PR 473. After a rebase this branch would carry no bump. Fixed in the rebase commit that follows: bump-version minor to 4.5.0, and spec §5.E and §5.G no longer claim 4.4.0 is unreleased.

<!-- fr:journal kind=finding scope=plan id=r5-m1-test-docstring created=2026-09-15T20:52:10 phase=5 state=fixed -->
### r5-m1-test-docstring · finding [fixed] · M1 Test docstring named a removed rule carrier (phase 5)

tests/unit/test_ste_output_tone.py line 1 now says the opt-in STE output style.

<!-- fr:journal kind=finding scope=plan id=r5-m2-tripwire-docstring created=2026-09-15T20:52:12 phase=5 state=fixed -->
### r5-m2-tripwire-docstring · finding [fixed] · M2 Hermes tripwire docstring re-wrapped (phase 5)

Rejoined the line; the file is identical to origin/main.

<!-- fr:journal kind=finding scope=plan id=r5-m3-style-subagent-scope created=2026-09-15T20:52:14 phase=5 state=fixed -->
### r5-m3-style-subagent-scope · finding [fixed] · M3 Opt-in style claimed subagent results (phase 5)

Output styles do not reach subagents. The Scope sentence now lists replies, status updates, skill announcements, PR bodies and journal entries. The filler tripwire reads only the Words section.

<!-- fr:journal kind=finding scope=plan id=r5-m4-prose-goal created=2026-09-15T20:52:16 phase=5 state=fixed -->
### r5-m4-prose-goal · finding [fixed] · M4 Plan prose Goal still described the forced style (phase 5)

Added a superseded note that points to the 2026-09-15 revision section.

<!-- fr:journal kind=finding scope=plan id=r5-m5-m6-no-action created=2026-09-15T20:52:17 phase=5 state=refuted -->
### r5-m5-m6-no-action · finding [refuted] · M5 and M6: no action (phase 5)

M5: phase 8 step P8.T2.S1 already moves ste-style-opt-in to skipped with a unit ref. M6: the title re-wrap by fr plan edit is harmless.

<!-- fr:journal kind=finding scope=plan id=p7-plan-exit-code-test created=2026-09-15T20:52:19 phase=5 state=fixed -->
### p7-plan-exit-code-test · finding [fixed] · Plan 07: exit-code test assumed a clean fixture (phase 5)

Found before dispatch: the _create_plan fixture has no skeleton marker, so self-review exits 1 without any prose. The planned test asserted exit 0. The test now compares against the clean plan's exit code. Spec §5.F wording updated.

<!-- fr:journal kind=discovery scope=plan id=2bbe0d69c345 created=2026-09-15T21:03:01 phase=6 -->
### 2bbe0d69c345 · discovery · complete-phase 6 warns on not-implemented acceptance rows (phase 6)

fr plan edit --complete-phase 6 prints a warning that journal-add-warns-on-long-prose and plan-self-review-warns-on-long-prose are still not-implemented. Expected: those rows are satisfied by phase 7 (wiring the lint into fr journal add and fr plan self-review), not phase 6 (the lint module itself). No action taken in phase 6.

<!-- fr:journal kind=finding scope=plan id=p8-plan-fr-goal-line-cap created=2026-09-15T21:06:21 phase=8 state=fixed -->
### p8-plan-fr-goal-line-cap · finding [fixed] · Plan 08: fr-goal reflow instruction would break the line cap (phase 8)

Found by a dry run before dispatch. The reporting contract adds 2 lines to fr-goal, which is at the 120-line cap. Reflowing only the §2 paragraph, as the step said, gives 121 lines. Reflowing the Interactive touchpoints paragraph as well gives 120. P8.T1.S2(a) now names both paragraphs.

<!-- fr:journal kind=finding scope=plan id=r6-i1-cross-wrap created=2026-09-16T06:53:27 phase=6 state=fixed -->
### r6-i1-cross-wrap · finding [fixed] · I1 Quotes and code spans paired wrongly across a line wrap (phase 6)

Stripping ran per line, so a span that wrapped deleted real prose between it and the next mark. Fix: split into items, flatten each item, then strip inline code, quotes and URLs. Verified on the reviewer case and on this repo own spec: 1 warning to 0.

<!-- fr:journal kind=finding scope=plan id=r6-i2-word-count created=2026-09-16T06:53:29 phase=6 state=fixed -->
### r6-i2-word-count · finding [fixed] · I2 Paths and dotted names inflated the word count (phase 6)

The old token pattern split on slash and dot, so one path counted as many words. Fix: a word is a whitespace token that contains a letter or digit; a lone dash counts as none. Spec section 5.C updated.

<!-- fr:journal kind=finding scope=plan id=r6-i3-closers created=2026-09-16T06:53:31 phase=6 state=fixed -->
### r6-i3-closers · finding [fixed] · I3 A closer after the end mark stopped the sentence split (phase 6)

Bold lead-ins and closing brackets or quotes after a period never split, so two sentences merged into one long count. Fix: the split accepts closers after a period, an exclamation mark or a question mark. The repo has 564 bold lead-ins.

<!-- fr:journal kind=finding scope=plan id=r6-i4-embed-end created=2026-09-16T06:53:33 phase=6 state=fixed -->
### r6-i4-embed-end · finding [fixed] · I4 A code line starting with END closed an embed early (phase 6)

Step P1.T1.S1 of 01.yaml embeds a code line that starts with END, which ended the block and linted the rest of the code as prose. Fix: an embed ends only at a bare END or at END with the same label. That step now reports 0 warnings, was 2.

<!-- fr:journal kind=finding scope=plan id=r6-i5-fences created=2026-09-16T06:53:34 phase=6 state=fixed -->
### r6-i5-fences · finding [fixed] · I5 Indented and longer fences were not stripped (phase 6)

The fence pattern needed column 0 and exactly three marks. Fix: allow indentation, three or more backticks or tildes, and close on the same run. An unclosed fence runs to the end of the text.

<!-- fr:journal kind=finding scope=plan id=r6-i6-markup created=2026-09-16T06:53:36 phase=6 state=fixed -->
### r6-i6-markup · finding [fixed] · I6 Self-review would crash on an excerpt with square brackets (phase 6)

plan_cmd prints issues with Rich markup on, so an excerpt with a closing tag raises MarkupError and breaks decision d9. Fixed in the phase 7 plan: step P7.T2.S2 adds markup off, and P7.T2.S1 adds a test. The change also restores the warn and error prefixes that Rich used to eat.

<!-- fr:journal kind=finding scope=plan id=r6-minors created=2026-09-16T06:53:38 phase=6 state=fixed -->
### r6-minors · finding [fixed] · Phase 6 minors fixed: M7 to M10, M12, M13, M14, M16, M17 (phase 6)

A heading needs a hash and a space (M7). Numbered lists with a bracket split (M8). CRLF front matter is stripped (M9). A quote that ends a sentence keeps its mark (M10). Nested and longer fences are stripped (M12). A filler inside a path or a hyphenated word is ignored (M13). The docstring states the real order (M14). The tripwire self-test runs the real comparison (M16). Tests were added for every case (M17). Tests: 20 to 48.

<!-- fr:journal kind=finding scope=plan id=r6-m11-m15 created=2026-09-16T06:53:40 phase=6 state=refuted -->
### r6-m11-m15 · finding [refuted] · M11 and M15: not fixed (phase 6)

M11, an unmatched quote eating the rest of a line, is covered in practice by the I1 flatten fix. M15, backtracking on thousands of unclosed openers, needs deliberately broken input and the lint only warns. The largest real spec lints in 12 ms.

<!-- fr:journal kind=discovery scope=plan id=9b2c50c5f5ac created=2026-09-16T07:04:48 phase=7 -->
### 9b2c50c5f5ac · discovery · RED counts for P7.T1.S1 and P7.T2.S1 differed slightly from the plan text (phase 7)

P7.T1.S1 RED was 2 failed, 2 passed, not 3 failed 1 passed as the plan text said: the idempotent re-add test and the clean-entry test both pass trivially before the warning code exists, since neither expects any warning text. P7.T2.S1 RED matched the plan exactly, 5 failed 1 passed. No code change needed either way; noting the variance for anyone re-running the steps.

<!-- fr:journal kind=finding scope=plan id=5c58c0defefa created=2026-09-16T07:05:00 phase=7 state=fixed -->
### 5c58c0defefa · finding [fixed] · test_plan_create_accepts_an_explicit_constraint_that_already_floors_at_4 fails because of this branch's 4.5.0 bump (phase 7)

Corrected by the orchestrator: the cause is this branch, not the repo before it. The test pins the ceiling at less than 4.5.0, and fr create parses the plan it just wrote, so the version gate refuses the running fr once that fr is 4.5.0. The 4.4.0 to 4.5.0 bump in commit 05eed2c is what crosses the ceiling, so CI on this PR would fail. Fixed here: the test now uses a ceiling of less than 5.0.0 and says why a pinned ceiling breaks on the release that reaches it.

<!-- fr:journal kind=discovery scope=plan id=cf68c8a8a6eb created=2026-09-16T07:05:11 phase=7 -->
### cf68c8a8a6eb · discovery · P7.T2.S1 test_markup_like_prose_does_not_crash_self_review needed a fixture tweak (phase 7)

As copied, the fixture text put the period right after the markdown link, so the sentence splitter (fixed in phase 6) split it into a short 5 word sentence holding the bracket text and a separate 30 word sentence with none of it. Only the long sentence gets an excerpt, so the excerpt never contained the bracket text and the test failed. Fix: drop the period after the link so the whole thing is one long sentence; the bracket text now sits inside the flagged excerpt. Behavior of the phase 6 lint is unchanged, only the test fixture.

<!-- fr:journal kind=finding scope=plan id=r7-i1-softwrap-journal created=2026-09-16T07:28:15 phase=7 state=fixed -->
### r7-i1-softwrap-journal · finding [fixed] · I1 The five-line cap printed 11 lines (phase 7)

Rich wraps at 80 columns off a TTY, so the five-warning cap wrapped into 11 physical lines and the test name promised more than it checked. Fix: soft wrap on both journal warning prints, and a test that counts physical lines.

<!-- fr:journal kind=finding scope=plan id=r7-i2-selfreview-wall created=2026-09-16T07:28:17 phase=7 state=fixed -->
### r7-i2-selfreview-wall · finding [fixed] · I2 Self-review printed a wall of wrapped text (phase 7)

On real plans each warn issue wrapped over 3 to 6 lines, so 16 of 22 printed lines were prose lint. Fix: soft wrap in plan_cmd, and the per-source excerpt cap cut from three to two. A new test asserts one physical line per issue.

<!-- fr:journal kind=finding scope=plan id=r7-i3-matrix-note created=2026-09-16T07:28:20 phase=7 state=fixed -->
### r7-i3-matrix-note · finding [fixed] · I3 The ci row note did not name the owed walk (phase 7)

The journal-add row now records that Test Plan step 5 is owed post-merge. My first edit put a bare colon inside the YAML note, which broke matrix.yaml parsing and made every fr command refuse with the migration gate message. Fixed by using a dash; fr validate artifacts and fr acceptance check pass.

<!-- fr:journal kind=finding scope=plan id=r7-m4-filler-labels created=2026-09-16T07:28:22 phase=7 state=fixed -->
### r7-m4-filler-labels · finding [fixed] · M4 Duplicate filler warnings were indistinguishable (phase 7)

A filler word in both title and body printed twice with no source. Each warning now carries title or body.

<!-- fr:journal kind=finding scope=plan id=r7-m5-read-errors created=2026-09-16T07:28:25 phase=7 state=fixed -->
### r7-m5-read-errors · finding [fixed] · M5 Unguarded spec read in the new code (phase 7)

The spec read in _prose_issues now uses errors=replace, so an odd encoding cannot raise out of a warn-only lint. The identical older read in _acceptance_link_issues predates this work and is left alone.

<!-- fr:journal kind=finding scope=plan id=r7-m6-backtracking created=2026-09-16T07:28:27 phase=7 state=fixed -->
### r7-m6-backtracking · finding [fixed] · M6 Inline-code pattern could backtrack (phase 7)

The lazy body made 20000 unmatched backticks take 174 seconds. Items are flattened before the strip, so a bounded body is enough. Fixed with a no-backtick body.

<!-- fr:journal kind=discovery scope=plan id=r7-m7-dogfood created=2026-09-16T07:28:30 phase=7 -->
### r7-m7-dogfood · discovery · M7 Dogfood record for step P7.T2.S3 (phase 7)

fr plan self-review on this plan exits 0 with exactly one prose warning, from plan step P8.T1.S2, a sentence of 26 words.

<!-- fr:journal kind=finding scope=plan id=r7-m8-weak-assert created=2026-09-16T07:28:32 phase=7 state=fixed -->
### r7-m8-weak-assert · finding [fixed] · M8 Weak assertion on the spec warning (phase 7)

The test matched any message containing the word spec. It now matches the full spec path label.

<!-- fr:journal kind=discovery scope=plan id=f358d88be10a created=2026-09-16T07:39:49 phase=8 -->
### f358d88be10a · discovery · Phase 8 ran exactly as dry-run predicted (phase 8)

All six RED tests failed as expected, the four skill edits produced 6 green tests plus test_skill_validation.py green, and the fr-goal reflow of both named paragraphs to width 95 landed the file at exactly 120 lines with no words removed. The explainer grep for the phrase short defense for each still matched line 329, so no explainer edit was needed. The acceptance gate (report, check, report check) passed with the five updated rows and no failing status.

<!-- fr:journal kind=finding scope=plan id=r8-i2-explainer-refs created=2026-09-16T07:58:58 phase=8 state=fixed -->
### r8-i2-explainer-refs · finding [fixed] · I2 Explainer line citations drifted after the fr-goal reflow (phase 8)

Five refs in docs/explainers/01-fr-goal.md pointed at shifted lines: the first paragraph is 16-34, the touchpoints paragraph 46-48, brainstorm 50-57 and spec-review 59-64. Fixed in the md. The html was regenerated with the blog-craft renderer from the filesystem root, after a byte-parity check proved the renderer reproduces the committed page from the unmodified source.

<!-- fr:journal kind=finding scope=plan id=r8-i3-fr-goal-table created=2026-09-16T07:59:00 phase=8 state=fixed -->
### r8-i3-fr-goal-table · finding [fixed] · I3 fr-goal still asked for a defense per row in the PR body (phase 8)

fr-acceptance presented mid-flight rows as a table while fr-goal line 111 still said each with a one-line defense for the same PR body block. fr-goal now says as one table with the same column list. The file is still 120 lines. The test pins each skill wording separately.

<!-- fr:journal kind=finding scope=plan id=r8-i4-row-status created=2026-09-16T07:59:02 phase=8 state=fixed -->
### r8-i4-row-status · finding [fixed] · I4 acceptance-rows-presented-as-table claimed ci on skill text alone (phase 8)

A skill-text assertion does not prove an agent obeys the skill, so the row is now skipped, like its sibling row. Spec section 7 Test Plan step 3 now also asks the operator to confirm that new rows arrive as one table, and the row notes cite it.

<!-- fr:journal kind=finding scope=plan id=r8-m5-test-gaps created=2026-09-16T07:59:04 phase=8 state=fixed -->
### r8-m5-test-gaps · finding [fixed] · M5 Reporting contract test was loose and asymmetric (phase 8)

The table assertion matched a bare token anywhere. Each skill now has its own sentence pinned, and the no-defense-per-row negative covers fr-brainstorming, fr-acceptance and fr-goal.

<!-- fr:journal kind=finding scope=plan id=r8-m6-install-guard created=2026-09-16T07:59:06 phase=8 state=fixed -->
### r8-m6-install-guard · finding [fixed] · M6 The new output-styles category had no install guard (phase 8)

Added tests/unit/test_install_copies_output_styles.py, modelled on the workflows guard: a style exists, the marketplace rsync excludes neither output-styles nor md files, and no shipped style forces itself on.

<!-- fr:journal kind=finding scope=plan id=r8-m7-commit-title created=2026-09-16T07:59:08 phase=8 state=refuted -->
### r8-m7-commit-title · finding [refuted] · M7 Duplicated title line in commit 1e4724b: left alone (phase 8)

The repo has no commit-message lint and the release tag comes from pyproject.toml. Rewriting a pushed branch to fix a cosmetic duplicate costs more than it returns.

<!-- fr:journal kind=finding scope=plan id=r8-i1-pr-body created=2026-09-16T08:18:00 phase=8 state=fixed -->
### r8-i1-pr-body · finding [fixed] · I1 PR 474 still advertised the deleted forced style (phase 8)

The deliver step ran at phase 4, before the 2026-09-15 reframe, so the body claimed a forced output style, a shipped rule, a phase-executor line and release 4.4.0. Fixed by running deliver again: the title and body are rebuilt from the durable journal and the current diff.

<!-- fr:journal kind=discovery scope=plan id=merge-main-4-12 created=2026-09-21T09:59:48 -->
### merge-main-4-12 · discovery · Merged origin/main at 4.12.0 into the branch

Seventeen commits landed on main while the PR was open. The operator chose a merge over a rebase, so every branch commit and the SHAs this journal cites stay intact. Generated files took main and were regenerated. Two tests main had fixed the same way took main. fr-goal took main and got the contract and the row table again, at 120 lines. journal_cmd took main and got the warning hook again. The matrix merged by row id. The run cursor migrated to schema 5. The version moved to 4.13.0.
