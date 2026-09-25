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
