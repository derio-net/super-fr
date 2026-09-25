# Journal: 2026-09-25-lean-cost-aware-process

<!-- fr:journal kind=discovery scope=plan id=1ad42589d6f1 created=2026-09-25T15:10:06 phase=1 -->
### 1ad42589d6f1 · discovery · no-refactor-because P1.T5 (phase 1)

Skill prose, install wiring, generated mirrors and a render check: no code structure to refactor.

<!-- fr:journal kind=discovery scope=plan id=526bcacc56d4 created=2026-09-25T19:37:52 phase=1 -->
### 526bcacc56d4 · discovery · Claude Code writes tool_use blocks on LATER records of a message (phase 1)

telemetry._distinct_messages drops every record after the first per message.id, which is right for summing usage but loses the tool_use blocks (usually written on later records). Added telemetry.message_groups (first record + all records of the id); _distinct_messages now delegates to it, so there is still one dedupe rule. cost-state token totals do NOT equal transcript sums (the harness counts side queries/compaction), so harness dollars are split, never reconstructed.

<!-- fr:journal kind=discovery scope=plan id=834e40db0862 created=2026-09-25T19:37:53 phase=1 -->
### 834e40db0862 · discovery · Model deviations: Cost.by_model, Message.agent, reader session arg (phase 1)

Cost gains by_model (per-model harness dollars — rollup divides each model's dollars, so it needs them); Message gains agent (main | subagent type) so subagent spend is attributable; UsageReader.read takes (source, session=None) because OpenCode/Hermes sources are a DB plus a session id. Claude Code cache writes without a TTL split book at the 1h rate (the audit prototype's convention); OpenCode's untyped cache.write books at 5m.

<!-- fr:journal kind=finding scope=plan id=83ed2919b8c4 created=2026-09-25T19:37:54 phase=1 state=open -->
### 83ed2919b8c4 · finding [open] · Hermes fixture rows are constructed, not captured (phase 1)

No Hermes host was available. tests/fixtures/usage/hermes/schema.sql is a verbatim copy of upstream SCHEMA_SQL (hermes-agent a3a85a31, SCHEMA_VERSION 30), but the rows, and the OpenAI-style messages.tool_calls JSON shape, are constructed against it. The reader tolerates both {function:{name,arguments}} and flat {name,arguments}. A live capture is owed before the Hermes reader is called verified.

<!-- fr:journal kind=discovery scope=plan id=485ac0f469c8 created=2026-09-25T19:55:49 phase=1 -->
### 485ac0f469c8 · discovery · Golden check: pooled 30.06% paperwork / 32.84% implementation (published 30.2 / 32.9) (phase 1)

tests/unit/test_usage_report.py::test_golden_audit_pooled_shares ran locally over the nine sessions (skipped in CI) and passes within 0.5 points. Getting there needed two classifier changes vs a first cut: stripped VAR=value prefixes are substituted into the rest of the command (F=docs/... && cat $F), and a shell write is classified by its path only when it lands in the repo's own trees. The rollup was drafted before its tests so the golden could calibrate it — a TDD order deviation for P1.T4.S1/S2; the tests were then written against the spec, not the code.

<!-- fr:journal kind=discovery scope=plan id=b6d0f33cd59d created=2026-09-25T19:55:49 phase=1 -->
### b6d0f33cd59d · discovery · Audit page render vs published per-session split: 7 of 9 within 0.5 points (phase 1)

fr usage report over the nine golden runs wrote ~/.cache/fr/usage/paper-trail.html. Pooled matches. Two sessions differ by more than 0.5: 05f4a8ab (paperwork 31.2 vs 30.6, implementation 38.7 vs 42.6) because its main transcript grew from 179 to 203 messages after the audit snapshot (data drift, same classification per call); and e50c7ff5 (21.9/29.4 vs 23.6/28.2) because the prototype approximated per-model dollars by each thread's model mix while the product prices each message by its own model — re-applying the prototype method to the product's classification reproduces 23.7/28.2. The product's figure is the more exact one; the published per-session figures were not re-derived.

<!-- fr:journal kind=discovery scope=plan id=f23e18967c66 created=2026-09-25T19:55:50 phase=1 -->
### f23e18967c66 · discovery · install.sh needs no per-skill wiring for fr-audit (phase 1)

scripts/install.sh copies every plugins/super-fr/skills/*/ by glob (Claude plugin, OpenCode, Hermes); SKILL_NAMES is the legacy stale-copy list. fr-audit ships by the glob; fr skills lists it (skills_cmd). Explainers currency: a new shipped skill — the explainer update is owed with the 4.x minor bump in phase 3, not done here.

<!-- fr:journal kind=discovery scope=plan id=674d801a6362 created=2026-09-25T19:55:57 phase=1 -->
### 674d801a6362 · discovery · no-refactor-because P1.T4 (phase 1)

rollup/render/usage_cmd are fresh modules written to the shape the tests pin; ruff/mypy clean, nothing duplicated to fold.

<!-- fr:journal kind=finding scope=plan id=7cf4d2239290 created=2026-09-25T19:56:21 phase=1 state=open -->
### 7cf4d2239290 · finding [open] · audit-pages-regenerated not flipped: no integration test of fr usage report yet (phase 1)

Phase 1's rows include audit-pages-regenerated (target int). The _prose says it flips on the unit AND integration tests of fr usage report; only unit CLI tests exist (tests/unit/test_usage_report.py) plus the local golden check. Notes recorded in the matrix; an integration test (e.g. tests/integration/ running fr usage report --format html over a fixture run) is owed before the flip.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-09-25T20:03:21 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · OpenCode reader labels every non-zero cost exact; Copilot-routed must be estimated (phase 1)

readers/opencode.py:128-137 vs spec §5.A.2.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-09-25T20:03:22 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Classifier tests pass even if unwrap/prefix-strip were a no-op; $VAR substitution untested (phase 1)

tests/unit/test_usage_classify.py:14-33.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-09-25T20:03:23 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · Hermes/OpenCode readers catch only sqlite3.Error; one bad row crashes the report (phase 1)

readers/hermes.py:93,118; opencode.py:63,72 vs spec §5.A.7.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-09-25T20:03:24 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · NULL per-model Hermes cost coerced to 0.0 and priced at $0 (phase 1)

hermes.py:105,111 + rollup.py:126-133.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-09-25T20:03:24 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · Mixed actual/estimated Hermes rows discard figures as Cost() none (phase 1)

hermes.py:101-114.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-09-25T20:03:25 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · .fr-deliver classified verify for shell writes but journal_write for Write tool (phase 1)

classify.py:127 vs :180.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-09-25T20:03:26 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · Report CLI test needle 'implement' matches the column header (phase 1)

tests/unit/test_usage_report.py:187.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-09-25T20:03:26 phase=1 state=open review_scope=in -->
### p1-r8 · finding [open] (reviewer: in scope) · report --run reads the cached index, missing sessions added to the cursor later (phase 1)

commands/usage_cmd.py:189-192.

<!-- fr:journal kind=finding scope=plan id=p1-r9 created=2026-09-25T20:03:27 phase=1 state=open review_scope=in -->
### p1-r9 · finding [open] (reviewer: in scope) · Unknown attempt harness relabelled claude-code (phase 1)

usage_cmd.py:88.

<!-- fr:journal kind=finding scope=plan id=p1-r10 created=2026-09-25T20:03:28 phase=1 state=open review_scope=in -->
### p1-r10 · finding [open] (reviewer: in scope) · Skill says count turns but the report renders none; phase 2 schema needs turns (phase 1)

fr-audit/SKILL.md:61-63, rollup.py:64.

<!-- fr:journal kind=finding scope=plan id=p1-r11 created=2026-09-25T20:03:28 phase=1 state=open review_scope=in -->
### p1-r11 · finding [open] (reviewer: in scope) · Golden test asserts only the pooled share, not the per-session 23-37% range (phase 1)

test_usage_report.py:232-239 vs spec §7.3.

<!-- fr:journal kind=finding scope=plan id=p1-r13 created=2026-09-25T20:03:29 phase=1 state=open review_scope=in -->
### p1-r13 · finding [open] (reviewer: in scope) · AGENTS.md repo shape has no fr/usage entry (phase 1)

AGENTS.md Repo shape.

<!-- fr:journal kind=finding scope=plan id=p2-r12 created=2026-09-25T20:03:30 phase=2 state=open review_scope=out -->
### p2-r12 · finding [open] (reviewer: out of scope) · UsageRecord.tool_calls targets hold raw commands/paths; phase 2 must serialize an allowlist projection (phase 2)

Filed against phase 2 from the phase-1 review (fr/usage/model.py:44-50); gates phase 2's review. Spec §5.B.2.

<!-- fr:journal kind=finding scope=plan id=83ed2919b8c4-resolved created=2026-09-25T20:03:30 state=open resolves=83ed2919b8c4 tracked_by=#623 -->
### 83ed2919b8c4-resolved · finding [deferred → #623] · resolves 83ed2919b8c4: Hermes fixture rows are constructed, not captured

No Hermes host available; spec §7.1 allows a schema-built fixture; live capture tracked.

<!-- fr:journal kind=review scope=plan id=r-p1 created=2026-09-25T20:03:31 phase=1 -->
### r-p1 · review · Phase 1 review (independent reviewer): 13 findings; r1-r11, r13 and 7cf4d2239290 fixed; r12 filed to phase 2; 83ed2919b8c4 deferred #623 (phase 1)

Reviewer a5ca54c59998f8557 (Opus 5.5) read every phase-1 file. Verified clean: dedupe single rule, harness-only pricing with fixed ratios, unavailable never 0, (prev, at] windows, READ_ONLY exemption, fixture privacy.

<!-- fr:journal kind=finding scope=plan id=p1-r13-resolved created=2026-09-25T20:21:36 state=fixed resolves=p1-r13 -->
### p1-r13-resolved · finding [fixed] · resolves p1-r13: AGENTS.md repo shape has no fr/usage entry

x

<!-- fr:journal kind=finding scope=plan id=p1-golden-e50 created=2026-09-25T20:22:05 phase=1 state=open -->
### p1-golden-e50 · finding [open] · Golden per-session paperwork share: e50c7ff5 reproduces 21.9% vs the audit's published 23.6% (phase 1)

The p1-r11 per-session assertion (23-37% within 0.5 points, spec §7.3) holds for 8 of 9 sessions. e50c7ff5 comes out at 21.9% against the audit page's own 23.6% (05f4a8ab is 0.6 off its published 30.6 but inside the band). A first-call-only attribution variant does not close it (21.4%). Most of the gap sits in single messages that carry a full 1h cache rebuild (one git/gh call is 5.5% of the session) and in memory/scratchpad file touches classified other. The audit's original classifier is not in the repo, so the difference cannot be pinned without it. Pinned as a STRICT xfail in tests/unit/test_usage_report.py (GOLDEN_OUTLIERS), not tuned away. Pooled shares still reproduce: paperwork 30.06% (published 30.2), implementation 32.84% (32.9).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-09-25T20:22:06 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: OpenCode reader labels every non-zero cost exact; Copilot-routed must be estimated

opencode.py: ESTIMATED_PROVIDERS (github-copilot prefix, confirmed against a live DB's providerIDs); a session is exact only if every priced message is. Fixture rows ses_copilot and ses_mixed (live row shape), NOTE.md sha updated; two tests.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-09-25T20:22:06 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Classifier tests pass even if unwrap/prefix-strip were a no-op; $VAR substitution untested

Added the reviewer's four shapes, but they pass even with _unwrap a no-op. So also added UNWRAP_DEPENDENT cases (isolation exec -- git, bash -lc 'git', GIT_PAGER=cat git, $F and ${F} heredoc writes to plan/code) and test_these_cases_need_the_unwrap, which monkeypatches _unwrap to identity and asserts each case changes answer.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-09-25T20:22:07 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: Hermes/OpenCode readers catch only sqlite3.Error; one bad row crashes the report

hermes.py and opencode.py: body moved to _read(); read() catches sqlite3.Error, then Exception, and returns unavailable (the claude_code.py pattern). Tests over DB copies: non-numeric token_count, bad timestamp, invalid UTF-8 (Hermes); overflowing timestamp, invalid UTF-8, text timestamp (OpenCode).

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-09-25T20:22:08 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: NULL per-model Hermes cost coerced to 0.0 and priced at $0

Hermes session_model_usage costs are NOT NULL DEFAULT 0, so 0 means not recorded. None and <=0 per-model figures are now omitted; with none left, by_model is empty and rollup takes the token-pool path. Test: all per-model zeros give by_model {} and nothing lands in unattributed.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-09-25T20:22:09 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: Mixed actual/estimated Hermes rows discard figures as Cost() none

hermes._cost: per session row, actual else estimated, summed; exact only if every row was actual. Per-model rows (now per session, no GROUP BY) follow their row's choice; a row with neither figure leaves the session unpriced. Tests for mixed rows and for a row with no figure.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-09-25T20:22:09 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: .fr-deliver classified verify for shell writes but journal_write for Write tool

Chose verify for both: .fr-deliver/ holds deliver's tests=<log>, the suite's own output, which the shell rule (like full*.log) already calls verify. _path now returns verify for .fr-deliver/ on Read/Write/Edit; table cases for Bash, Write and Read. Golden re-run unchanged: pooled paperwork 30.06%, implementation 32.84%.
