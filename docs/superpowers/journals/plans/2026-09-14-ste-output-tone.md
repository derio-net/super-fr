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
