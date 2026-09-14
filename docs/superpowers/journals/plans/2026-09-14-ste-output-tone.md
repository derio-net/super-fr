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
