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

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-09-25T20:22:10 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: Report CLI test needle 'implement' matches the column header

The CLI test asserts a line-anchored By-step row per step (step cell then a dollar cell), and a new rollup test asserts by_step keys are exactly the cursor steps the fixture's messages fall in (plus OUTSIDE).

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-09-25T20:22:11 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: report --run reads the cached index, missing sessions added to the cursor later

report --run takes the union of the cached index and the live cursor's sessions (fails only when neither exists). Test: collect, append a session to the cursor, report shows both.

<!-- fr:journal kind=finding scope=plan id=p1-r9-resolved created=2026-09-25T20:22:11 state=fixed resolves=p1-r9 -->
### p1-r9-resolved · finding [fixed] · resolves p1-r9: Unknown attempt harness relabelled claude-code

_sessions_of defaults to claude-code only when the attempt names no harness; read_session returns unavailable 'no reader for this harness' for an unknown one; UsageRecord.harness widened to str. Test with a codex attempt and a harness-less one.

<!-- fr:journal kind=finding scope=plan id=p1-r10-resolved created=2026-09-25T20:22:12 state=fixed resolves=p1-r10 -->
### p1-r10-resolved · finding [fixed] · resolves p1-r10: Skill says count turns but the report renders none; phase 2 schema needs turns

Rollup.turns_by_activity (a message is one turn of each activity it touched, priced or not) and turns_by_step (one per message), rendered as turns columns in By activity and By step (table and html). fr-audit skill text says the report counts them; OpenCode and Hermes mirrors regenerated.

<!-- fr:journal kind=finding scope=plan id=p1-r11-resolved created=2026-09-25T20:22:13 state=fixed resolves=p1-r11 -->
### p1-r11-resolved · finding [fixed] · resolves p1-r11: Golden test asserts only the pooled share, not the per-session 23-37% range

Added test_golden_audit_every_sessions_paperwork_share_is_23_to_37, parametrized per session, band [22.5, 37.5]. Re-run: 31.2 34.0 30.5 22.7 21.9 37.2 31.9 37.0 36.0. e50c7ff5 (21.9 vs published 23.6) is a strict xfail, journaled as open finding p1-golden-e50 rather than tuned away.

<!-- fr:journal kind=finding scope=plan id=p1-r13-resolved-2 created=2026-09-25T20:22:13 state=fixed resolves=p1-r13 -->
### p1-r13-resolved-2 · finding [fixed] · resolves p1-r13: AGENTS.md repo shape has no fr/usage entry

Supersedes the placeholder note 'x' (a diagnostic call). AGENTS.md Repo shape: fr/usage entry after fr/triage (readers, classify, rollup, render, CLI, cache location, READ_ONLY, fr-audit).

<!-- fr:journal kind=finding scope=plan id=7cf4d2239290-resolved created=2026-09-25T20:22:14 state=fixed resolves=7cf4d2239290 -->
### 7cf4d2239290-resolved · finding [fixed] · resolves 7cf4d2239290: audit-pages-regenerated not flipped: no integration test of fr usage report yet

tests/integration/test_usage_report_cli.py runs the real fr console script (report --run --format html -o) over a temp git repo with a v6 cursor, FR_TRANSCRIPT_ROOT at the committed fixture, HOME and cache in tmp. It asserts the five sections, By-step rows, the dash row for a missing session, no $0, and an untouched repo. audit-pages-regenerated set to ci with the int level; usage-reconstruct-cross-harness notes now cite #623. Also: sub-cent figures render <$0.01, not $0.00.

<!-- fr:journal kind=finding scope=plan id=p1-golden-e50-resolved created=2026-09-25T20:24:04 state=refuted resolves=p1-golden-e50 -->
### p1-golden-e50-resolved · finding [refuted] · resolves p1-golden-e50: Golden per-session paperwork share: e50c7ff5 reproduces 21.9% vs the audit's published 23.6%

Not a defect: the product prices each message by its own model (spec §5.A.2); the published 23.6% came from the prototype's thread-level model-mix approximation, which the product reproduces when that method is applied. The test now pins the correct per-message figure (21.9±0.5).

<!-- fr:journal kind=finding scope=plan id=p2-r12-resolved created=2026-09-25T20:33:53 state=fixed resolves=p2-r12 -->
### p2-r12-resolved · finding [fixed] · resolves p2-r12: UsageRecord.tool_calls targets hold raw commands/paths; phase 2 must serialize an allowlist projection

fr.usage.file.session_entry/dump_usage build plain mappings field by field (no model_dump of a UsageRecord); tests/unit/test_usage_kind.py::test_a_capture_serializes_no_host_url_path_or_content feeds a record whose tool-call targets hold a hostname, ~/ path, /Users path and URL and asserts none reach the YAML

<!-- fr:journal kind=discovery scope=plan id=p2-capture-rules created=2026-09-25T20:43:55 phase=2 -->
### p2-capture-rules · discovery · Capture decisions: new-host resolve needs a session; same-host re-capture keeps earlier readable figures; briefs deferred (phase 2)

(1) A first resolve on a host captures only when there is at least one candidate session (otherwise every run's first resolve would write an empty file); deliver always writes. (2) One capture per host holds, but a re-capture (e.g. closeout on the delivering host) keeps a session's earlier entry when the new read is unavailable, and keeps sessions it no longer sees - a replace must not turn a measurement into an absence. (3) SessionEntry.briefs exists in the schema but capture does not fill it yet: Claude Code tool targets carry no prompt text; phase 3's step records are where fr knows brief sizes itself. (4) read_session/sessions_of moved from usage_cmd to fr/usage/sources.py so capture and fr usage share one lookup rule.

<!-- fr:journal kind=decision scope=plan id=p2-run7-shape created=2026-09-25T21:12:11 phase=2 -->
### p2-run7-shape · decision · Run 6->7: migrated capture uses a pseudo-host, live captures supersede it; runner commits companion files (phase 2)

(1) The migrated capture's host label is host_label(run, '(migrated)') so it never occupies (and is never replaced by) a real host's entry; captured_at is the cursor's latest step at, so the migration is deterministic across machines. (2) fr run cost reads live captures and falls back to migrated figures only when no live capture read any session - otherwise subagent tokens would be counted twice (the Claude Code reader already folds subagent transcripts into the session). (3) SchemaMigration.fn may now return the companion paths it wrote; PlannedAction.also_wrote feeds changed_paths so fr migrate / the CLI gate commit the usage file with the cursor. (4) Figure.turns became optional: a migrated subagent entry knows its step but not its turns, and unknown is never 0. (5) The 4->5 crash-window check and the 5->6 guard now read with RunStateV6; the ONE live-parser use under fr/artifacts/run_*.py is run_usage_split's crash-window fallback (tripwire re-pointed). (6) archive._read_any_version tries RunStateV6 before V4 - without it every v6 cursor looked like no cursor and fr migrate offered to re-adopt its plan.

<!-- fr:journal kind=discovery scope=plan id=p2-matrix-ref-edit created=2026-09-25T21:12:12 phase=2 -->
### p2-matrix-ref-edit · discovery · Deviation: one matrix ref removed by hand (no verb removes a level) (phase 2)

Deleting tests/unit/test_run_main_session.py (it tested the removed main_session measurement) left row fr-goal-main-session-cost citing a missing file, which fails fr acceptance check. fr acceptance set-status can only ADD levels, so that one ref line was removed by hand, then the row was re-pointed with the T7.S2 set-status command (level test_usage_capture.py) - done in T4 so the suite stayed green; set-status regenerated the reports. Telemetry's attempt-measurement code (measure_attempt / measure_dispatch / TranscriptReader.measure) is left in place with no caller in run_cmd; main-session measurement was deleted with its model.

<!-- fr:journal kind=discovery scope=plan id=p2-backfill-rule created=2026-09-25T21:14:15 phase=2 -->
### p2-backfill-rule · discovery · Backfill: transcripts win, else the cursor's own figures (phase 2)

Per archived run: if any session the cursor names is readable here, the backfill capture is those sessions read (exact dollars where kept); otherwise the cursor's own figures (v5/v6 estimate/measured/main_session via split_usage, v1-v4 accounting via v4_to_v5 first) are carried with usd_source none beside the unavailable sessions. A run that already has a usage file (active or archived) is skipped, so a re-run is a no-op; archived cursors are only read. no-refactor-because: P2.T5 - one fresh module shaped by its tests.

<!-- fr:journal kind=decision scope=plan id=p2-host-side created=2026-09-25T21:24:10 phase=2 -->
### p2-host-side · decision · Host-side rule: conftest neutralises the container probe; unobserved is an evidence key (phase 2)

(1) Many test fixtures are real linked worktrees with a mode: worktree marker, so a suite run inside this repo's own devcontainer would have every fr run refused. tests/conftest.py patches fr.isolation.where.container_evidence to False for the whole suite; the rule's own tests patch it back. The product rule stays marker+evidence, never an env bypass. (2) The in-process host command prints the marker's recorded toplevel (devcontainers mount the workspace at its host path, scaffold.py), and the argv tail from the group on (sys.argv; Typer gives a group callback no args). (3) Unobserved gates record evidence key 'unobserved' = comma-separated gate names (reviewer, tests, operator-gate) on the resolved unit, and every warning line names it. The operator-gate warning now also fires with NO harness detected, not only on Claude Code; OpenCode/Hermes still rely on advance's degradation notice. (4) The OpenCode plugin gates no bash call, so its host-side test only pins that the form passes.

<!-- fr:journal kind=decision scope=plan id=p2-parity-modes created=2026-09-25T21:30:58 phase=2 -->
### p2-parity-modes · decision · Parity modes: harness state stays required, modes refine; main-session-cost row retired for usage-capture (phase 2)

HarnessState keeps its required state (what fr harness parity --check compares against registration files, which do not vary by mode) and gains optional modes {host-worktree|devcontainer|external: {state, scope_note}}; state_in(mode) falls back to the harness state. usage-capture is partial on all three harnesses until phase 4's live walk (claude-code, opencode), Hermes stays partial (implemented, not live-verified). main-session-cost was removed rather than re-described: it named StepRecord.main_session, which run 7 deleted. Also flipped usage-readable-on-any-host to ci (test_run_cost_cmd's checkout-that-never-ran-it test) beyond the two rows the plan named - the acceptance rule requires it once a test verifies a row. AGENTS.md repo shape updated for fr/usage persistence and the host-side rule.

<!-- fr:journal kind=finding scope=plan id=p2-r20 created=2026-09-25T21:40:21 phase=2 state=open review_scope=in -->
### p2-r20 · finding [open] (reviewer: in scope) · In-process refusal blocks host-worktree pods/CI: mode: worktree + container evidence is not devcontainer (phase 2)

isolation/where.py:122, masked by tests/conftest.py:162-175. Spec §5.B.6 amended: marker records target; refuse iff target devcontainer + container evidence.

<!-- fr:journal kind=finding scope=plan id=p2-r21 created=2026-09-25T21:40:21 phase=2 state=open review_scope=in -->
### p2-r21 · finding [open] (reviewer: in scope) · unavailable reason copies exception text (absolute paths, usernames) into committed usage files (phase 2)

usage/file.py:241-242; readers' f'{type(exc).__name__}: {exc}'.

<!-- fr:journal kind=finding scope=plan id=p2-r22 created=2026-09-25T21:40:22 phase=2 state=open review_scope=in -->
### p2-r22 · finding [open] (reviewer: in scope) · fr run cost drops all migrated entries once any live capture exists (phase 2)

run/cost.py:87-93: supersede per session/step, report ignored entries.

<!-- fr:journal kind=finding scope=plan id=p2-r23 created=2026-09-25T21:40:23 phase=2 state=open review_scope=in -->
### p2-r23 · finding [open] (reviewer: in scope) · Dispatched reviewer attempts (agent, no agent_type) labelled role: main (phase 2)

artifacts/run_usage_split.py:109-114; regenerate both committed usage files.

<!-- fr:journal kind=finding scope=plan id=p2-r24 created=2026-09-25T21:40:23 phase=2 state=open review_scope=in -->
### p2-r24 · finding [open] (reviewer: in scope) · Capture never fills briefs (phase 2)

usage/capture.py:166-171: measure dispatch-prompt size from the parent transcript's Agent tool_use input; keep migrated handoff_chars.

<!-- fr:journal kind=finding scope=plan id=p2-r25 created=2026-09-25T21:40:24 phase=2 state=open review_scope=in -->
### p2-r25 · finding [open] (reviewer: in scope) · fr-goal-main-session-cost still cites tests of the removed mechanism (phase 2)

matrix.yaml:4010-4016; remove stale refs; verb tracked in https://github.com/derio-net/super-fr/issues/624.

<!-- fr:journal kind=finding scope=plan id=p2-r26 created=2026-09-25T21:40:24 phase=2 state=open review_scope=in -->
### p2-r26 · finding [open] (reviewer: in scope) · Runner companion paths: uncommitted if the stamp fails; uncommitted_veto ignores them (phase 2)

artifacts/runner.py:527-550, trigger.py:477: declare companion paths up front; carry also_wrote on FailedAction.

<!-- fr:journal kind=finding scope=plan id=p2-r27 created=2026-09-25T21:40:25 phase=2 state=open review_scope=in -->
### p2-r27 · finding [open] (reviewer: in scope) · measure_dispatch/measure_attempt/TranscriptReader.measure left without a caller (phase 2)

run/telemetry.py:1000-1075 (+551, 628, 935): delete with their tests.

<!-- fr:journal kind=finding scope=plan id=p2-r28 created=2026-09-25T21:40:26 phase=2 state=open review_scope=in -->
### p2-r28 · finding [open] (reviewer: in scope) · Operator-gate unobserved recorded only on claude-code/no harness (phase 2)

commands/run_cmd.py:985-986 vs spec §5.B.7.

<!-- fr:journal kind=finding scope=plan id=p2-r29 created=2026-09-25T21:40:26 phase=2 state=open review_scope=in -->
### p2-r29 · finding [open] (reviewer: in scope) · Closeout upsert erases the deliver capture record (phase 2)

archive.py:505; spec amended: at becomes a list of events per host.

<!-- fr:journal kind=finding scope=plan id=p2-r30 created=2026-09-25T21:40:27 phase=2 state=open review_scope=in -->
### p2-r30 · finding [open] (reviewer: in scope) · usage group checks cwd repo, not the subcommand's --repo (phase 2)

commands/usage_cmd.py:54.

<!-- fr:journal kind=review scope=plan id=r-p2 created=2026-09-25T21:40:37 phase=2 -->
### r-p2 · review · Phase 2 review (independent reviewer): 11 findings (p2-r20..r30), all in scope; spec §5.B.1/3/6 amended for r20 and r29 (phase 2)

Reviewer a72e52c7973e5ac63 (Opus 5.5). Verified clean: _read_any_version order, parity row replacement, host label + field-by-field allowlist, capture in the cursor commit and never failing its step, archive move, backfill read-only, RunStateV6 freeze + frozen hops, bridge refusal only in devcontainer with the right uv run fr/fr form, external never refused. Blocker: p2-r20 (host-worktree pods refused).

<!-- fr:journal kind=discovery scope=plan id=p2-d-review-fixes created=2026-09-25T22:15:26 phase=2 -->
### p2-d-review-fixes · discovery · Phase-2 review fixes: live shapes captured, one pre-existing gap noted (phase 2)

Briefs (p2-r24): the OpenCode task part shape (state.input.prompt, state.metadata.sessionId/parentSessionId) was read from this operator's live opencode.db (key shapes and sizes only) before writing the reader; the Claude Code fixture gained its two real Agent prompts as same-length placeholders (96, 2480 chars) from the same source transcript; NOTE.md records both and the new sha256s. Committed usage files regenerated through split_run_usage over the eab566e9^ v6 cursors plus capture() for this host (figures reflect the orchestrator session at recapture time). Pre-existing gap, not fixed: the kind: cli gate-clear branch of fr run resolve never persists _take_unobserved() (the cli step record has no unit to carry evidence), so unobserved=operator-gate reaches stderr but not the cursor there; agent-kind gates (fr-goal's brainstorm) record it. Conftest container_evidence patch dropped: the full suite passes with evidence forced on.

<!-- fr:journal kind=finding scope=plan id=p2-r20-resolved created=2026-09-25T22:15:58 state=fixed resolves=p2-r20 -->
### p2-r20-resolved · finding [fixed] · resolves p2-r20: In-process refusal blocks host-worktree pods/CI: mode: worktree + container evidence is not devcontainer

aaf707cf: fr isolation up writes target (devcontainer|worktree) beside unchanged mode; require_harness_host refuses iff target devcontainer + container evidence; legacy marker never refused. Edit-gate readers (Claude Code, Hermes, OpenCode bun) tested with the key. Conftest patch dropped: full suite green with evidence forced on.

<!-- fr:journal kind=finding scope=plan id=p2-r21-resolved created=2026-09-25T22:15:59 state=fixed resolves=p2-r21 -->
### p2-r21-resolved · finding [fixed] · resolves p2-r21: unavailable reason copies exception text (absolute paths, usernames) into committed usage files

1facaa02: session_entry maps unavailable through committed_reason, a closed vocabulary (known constants incl. ACP verbatim, else reader failed[: ExcType|database unreadable|unreadable transcript]); a PermissionError on a /Users path leaves no path in the committed YAML.

<!-- fr:journal kind=finding scope=plan id=p2-r22-resolved created=2026-09-25T22:16:00 state=fixed resolves=p2-r22 -->
### p2-r22-resolved · finding [fixed] · resolves p2-r22: fr run cost drops all migrated entries once any live capture exists

9e1ec7c2: effective_entries ignores a migrated entry only when a live capture read its session or covers every step it names; partly covered keeps uncovered steps (tokens dropped); fr run cost prints N migrated entries ignored. Tested with an unrelated live closeout session.

<!-- fr:journal kind=finding scope=plan id=p2-r23-resolved created=2026-09-25T22:16:00 state=fixed resolves=p2-r23 -->
### p2-r23-resolved · finding [fixed] · resolves p2-r23: Dispatched reviewer attempts (agent, no agent_type) labelled role: main

9e1ec7c2: split_usage maps an attempt with agent but no agent_type to role subagent; both committed usage files regenerated through split_run_usage (v6 cursors at eab566e9^) plus capture().

<!-- fr:journal kind=finding scope=plan id=p2-r24-resolved created=2026-09-25T22:16:01 state=fixed resolves=p2-r24 -->
### p2-r24-resolved · finding [fixed] · resolves p2-r24: Capture never fills briefs

9e1ec7c2: readers measure dispatch prompt sizes (Claude Code Agent tool_use input.prompt keyed by attributed agent id; OpenCode task part state.input.prompt keyed by state.metadata.sessionId, shape read from a live db); session_entry re-keys to the cursor unit holding that agent. Migrated handoff_chars briefs stay in their migrated capture (files never rewritten).

<!-- fr:journal kind=finding scope=plan id=p2-r25-resolved created=2026-09-25T22:16:02 state=fixed resolves=p2-r25 -->
### p2-r25-resolved · finding [fixed] · resolves p2-r25: fr-goal-main-session-cost still cites tests of the removed mechanism

a97bbe1c: three stale refs removed one hand-edited line each (no drop-level verb: #624), set-status --notes records why, reports regenerated (--deterministic).

<!-- fr:journal kind=finding scope=plan id=p2-r26-resolved created=2026-09-25T22:16:02 state=fixed resolves=p2-r26 -->
### p2-r26-resolved · finding [fixed] · resolves p2-r26: Runner companion paths: uncommitted if the stamp fails; uncommitted_veto ignores them

e88deb21: SchemaMigration.companions declared up front (run 6->7 declares usage/<run>.yaml) and checked by the veto; FailedAction.also_wrote carries companions written before a failed stamp (write_version raising now caught too); gate and fr migrate print them. Tests for both gaps plus an e2e uncommitted_veto case.

<!-- fr:journal kind=finding scope=plan id=p2-r27-resolved created=2026-09-25T22:16:03 state=fixed resolves=p2-r27 -->
### p2-r27-resolved · finding [fixed] · resolves p2-r27: measure_dispatch/measure_attempt/TranscriptReader.measure left without a caller

a268b717: measure_dispatch, measure_attempt, TranscriptReader(.measure) and the readers' measure/locate_session deleted with what only they used (Measurement, select_*, reader_for/READERS, read_claude_code, UsageTotals, ...) and their tests; kept _read_records, message_groups, attribute_dispatches, gates, dispatched_from_this_session.

<!-- fr:journal kind=finding scope=plan id=p2-r28-resolved created=2026-09-25T22:16:03 state=fixed resolves=p2-r28 -->
### p2-r28-resolved · finding [fixed] · resolves p2-r28: Operator-gate unobserved recorded only on claude-code/no harness

ea8a6b46: operator gate records unobserved=operator-gate and warns on every harness without a question reader (opencode, hermes tested); warning names the harness.

<!-- fr:journal kind=finding scope=plan id=p2-r29-resolved created=2026-09-25T22:16:04 state=fixed resolves=p2-r29 -->
### p2-r29-resolved · finding [fixed] · resolves p2-r29: Closeout upsert erases the deliver capture record

9e1ec7c2: Capture.at is a non-empty list of distinct events; capture() appends to the host's entry so closeout keeps deliver; usage kind v1 unreleased, no migration; fixtures/tests and both committed files updated.

<!-- fr:journal kind=finding scope=plan id=p2-r30-resolved created=2026-09-25T22:16:05 state=fixed resolves=p2-r30 -->
### p2-r30-resolved · finding [fixed] · resolves p2-r30: usage group checks cwd repo, not the subcommand's --repo

9d5b80df: host-side check moved from the usage group callback into each subcommand, against its --repo (else the resolved repo root); test with a marked --repo and a plain cwd and vice versa.

<!-- fr:journal kind=decision scope=plan id=p3-engine-shape created=2026-09-25T22:41:19 phase=3 -->
### p3-engine-shape · decision · Record engine: validate+build in memory, write, run resolve's own gates, restore on refusal (phase 3)

(1) Every record-level check (sections vs emits, tick/finding ids, duplicates, entry shape, matrix rows, plan re-parse in a scratch copy) runs before any byte moves. The step's EXISTING gates (review witness, findings/operator guard, tests= log, refactor) read the journal and plan from disk, so the engine writes its overlay atomically first and then runs resolve's own body in process (run_cmd.resolve_in_process -> _resolve_body); a gate refusal restores every touched path byte-for-byte. Observable contract holds: a refusal changes nothing, a success is one commit. (2) Beyond the spec §5.C.1 example the model carries emitted (always allowed, validated by resolve's own --emitted rule — brainstorm/plan/deliver need it), complete (grouped with ticks under plan:ticks, for the --complete-phase verb) and richer entry fields (resolves/tracked_by/answered_by/global) so the verbs' flags fit one-entry records. (3) A plan:ticks unit resolved done completes its phase (refuses on unticked steps). (4) outcome blocked resolves failed and says so. (5) refactor reasons are journalled as 'no-refactor-because P<n>.T<m>' discoveries, which is also what the resolve-time gate reads, so pre-record journal entries satisfy it unchanged (back-compat). (6) evidence.answered_by is passed as --answered-by. (7) The body's own stdout is held; lines after its first (group-done, deliver closeout) go to stderr so stdout is the one line.

<!-- fr:journal kind=discovery scope=plan id=p3-t2-order created=2026-09-25T22:41:20 phase=3 -->
### p3-t2-order · discovery · Deviation: T2 engine written before its tests; red confirmed against the stashed baseline (phase 3)

The apply engine and run_cmd wiring were drafted before tests/unit/test_record_apply.py. Red was then confirmed by stashing run_cmd.py/plan_ops.py and running the new tests (12 failed: no --record flag, self-review refactor gate) before restoring. Only tests/unit/test_v2_plan_ops.py's self-review refactor tests changed in the rest of the suite (rewritten against fr.record.gates.refactor_gaps; the fully-ticked exemption is dropped since at resolve every task is ticked).

<!-- fr:journal kind=discovery scope=plan id=p3-verbs created=2026-09-25T22:48:11 phase=3 -->
### p3-verbs · discovery · Verbs via the engine: acceptance verbs now commit; journal add prints a line (phase 3)

fr acceptance add/set-status previously wrote without committing; through the engine they commit once (matrix + three reports) like every other record write. fr journal add previously printed nothing on stdout; it now prints 'added <kind> <id> to <scope>/<slug>'. Refusals the verbs already had stay in the verbs (duplicate id, --phase/--global, answered-by operator transcript check, unknown row/status) so their messages are byte-identical; the engine re-checks and refuses anything else with exit 2. The now-dead acceptance helpers _commit_matrix/_regenerate_reports were removed.

<!-- fr:journal kind=decision scope=plan id=p3-template created=2026-09-25T22:52:46 phase=3 -->
### p3-template · decision · Template: brief key 'record' {path, template, in_progress}; pickup finds the run by its emitted plan (phase 3)

Every agent-step brief gains 'record' (null for a fan-out group; each member brief carries its own). fr pickup <plan> --phase N appends '## Step record' only when a live cursor under docs/superpowers/runs/ recorded this plan as emitted: the template of the first for_each member whose emits carry plan:ticks, or 'record in progress: N ticks, M decisions — <path>' when the file exists. The runner path (no cursor) shows nothing and keeps using the verbs. Deviation: T4 code drafted before its tests; red confirmed (KeyError record / no Step record section) before wiring.

<!-- fr:journal kind=decision scope=plan id=p3-pr-body created=2026-09-25T23:00:10 phase=3 -->
### p3-pr-body · decision · PR body: rendered on the record path of a step that emits pr; the flag path stays unchecked (phase 3)

resolve --record for a step emitting 'pr' (manifest-driven, fr-goal's deliver) with outcome done renders docs/superpowers/runs/<run>.records/pr-body.md (Findings, Out-of-scope findings or None., Proportionality, Cost), then reads the live body with fr.gh.view_pr_body(emitted.pr or the branch). An unreadable PR or a missing heading refuses (exit 2); the render is the one file a refusal leaves, untracked, since the agent opens the PR with it; on success it is deleted with the record. Cost reads the usage file if present, else this host's transcripts (not written). The plain '--state done' deliver path is NOT gated: it serves humans/runners and a dozen existing tests; the pipeline skills now teach only the record path. Full suite: 5436 passed; one parallel-load flake in test_opencode_plugin_live (passes alone).

<!-- fr:journal kind=discovery scope=plan id=p3-t6-norefactor created=2026-09-25T23:13:30 phase=3 -->
### p3-t6-norefactor · discovery · no-refactor-because P3.T6 (phase 3)

Prose, mirrors, explainer, version bump and matrix flips: nothing to extract — the edits are generated (mirrors, report set, rendered page) or one-line prose substitutions.

<!-- fr:journal kind=discovery scope=plan id=p3-prose created=2026-09-25T23:13:32 phase=3 -->
### p3-prose · discovery · Prose: record flow taught; three prose tests re-pointed; audit row already ci (phase 3)

fr-goal (110 lines) teaches one resolve --record per step (spec-review: the reviewer's return is the record; review-phase: evidence {review, reviewer, model}; deliver: fr renders pr-body.md, draft PR opened with it, host-side rule for devcontainer). fr-brainstorming records decisions and acceptance rows in the brainstorm record; fr-plan says the refactor reason is a record field and the gate is at resolve; fr-execute points at pickup's '## Step record' and keeps the verbs for the runner path; fr-debugging notes a verb is a one-entry record; fr-phase-executor keeps the record and returns its path; fr-spec-reviewer returns record-shaped YAML. Record evidence also accepts agent/harness/model (the late-identity flags). Tests re-pointed to the new prose: test_fr_goal_journal (pr-body.md/--record instead of fr journal render), test_run_resolve_requires_advance (model: <the model you are running on>), test_skill_journal_resolve_examples (fr-goal keeps one runnable resolve example, the closeout deferral; threshold 3 -> 1). Explainer: unmodified re-render byte-identical first, then the three edited paragraphs (records, usage/ replacing the removed main-session measurement, rendered PR body) plus the fr-audit line. audit-pages-regenerated was already ci (phase 1), so four rows flipped, not five. AGENTS.md: fr/record entry; stale 'conftest neutralises the probe' replaced by the target: devcontainer rule.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-09-25T23:23:32 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · Record path accepts answered_by: operator on an out-of-scope fix without transcript verification (phase 3)

record/apply.py:302,329,356; journal_cmd.py:314,474; before_write hook never set. Move _verify_operator_claim into fr.journal, call in _journal_writes for both paths.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-09-25T23:23:33 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · Plain resolve --step deliver --state done bypasses the live PR-section check (phase 3)

apply.py:683 vs run_cmd.py:3981; spec §5.C.4 / Test Plan 13. Check inside _resolve_body deliver/done branch.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-09-25T23:23:33 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · Invalid-record atomicity: crash window, retry wedges on existing ids, restore misses cursor/usage paths and can revert committed files (phase 3)

apply.py:701-732, run_cmd.py:3979-3996. Orchestrator decision: delete record after commit; byte-identical re-append is a no-op (retry heals); snapshot every _RunWrites.note path; never restore after a commit landed.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-09-25T23:23:34 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · --record silently ignores --no-questions/--reason/--answered-by/--agent/--harness/--model (phase 3)

run_cmd.py:3701-3710. Refuse them with --record, or add no_questions/reason record fields and document the gate bypass in fr-goal §1.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-09-25T23:23:35 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · Record acceptance entries create-or-move by id existence, losing add/set-status refusals (phase 3)

apply.py:520-566. capability/acceptance present = create-only; absent = move-only.

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-09-25T23:23:35 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · fr-goal SKILL.md:96 claims record-path answered_by verification that does not exist (phase 3)

Made true by p3-r1.

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-09-25T23:23:36 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · No test that deliver's tests= log gate still fires through --record (phase 3)

tests/unit/test_record_apply.py; P3.T2.S1(c).

<!-- fr:journal kind=finding scope=plan id=p3-r8 created=2026-09-25T23:23:37 phase=3 state=open review_scope=in -->
### p3-r8 · finding [open] (reviewer: in scope) · fr plan edit --complete-phase no longer enforces the refactor check (phase 3)

apply.py:445-465 + prose in fr-phase-executor.md:82-88, fr-execute SKILL.md:55. Call refactor_gaps in _plan_writes on any phase completion.

<!-- fr:journal kind=finding scope=plan id=p3-r9 created=2026-09-25T23:23:37 phase=3 state=open review_scope=in -->
### p3-r9 · finding [open] (reviewer: in scope) · --record deletes and commits any parseable path; relative path resolved against cwd (phase 3)

apply.py:687-694, run_cmd.py:4120. Resolve against repo root, require under records_dir(run).

<!-- fr:journal kind=finding scope=plan id=p3-r10 created=2026-09-25T23:23:38 phase=3 state=open review_scope=in -->
### p3-r10 · finding [open] (reviewer: in scope) · Successful resolve prints a second stderr line (fr: committed …) (phase 3)

records_commit.py:68. Suppress when the engine owns the line.

<!-- fr:journal kind=finding scope=plan id=p3-r11 created=2026-09-25T23:23:39 phase=3 state=open review_scope=out -->
### p3-r11 · finding [open] (reviewer: out of scope) · test_opencode_plugin_live flaky under parallel load (phase 3)

Not caused by this change; not touched by the diff.

<!-- fr:journal kind=finding scope=plan id=p3-r11-resolved created=2026-09-25T23:23:39 state=open resolves=p3-r11 out_of_scope=true -->
### p3-r11-resolved · finding [out-of-scope] · resolves p3-r11: test_opencode_plugin_live flaky under parallel load

Pre-existing live-plugin test; this diff does not touch it; observed once under -n auto load, green alone and in the final run.

<!-- fr:journal kind=review scope=plan id=r-p3 created=2026-09-25T23:23:40 phase=3 -->
### r-p3 · review · Phase 3 review (independent reviewer): 11 findings; p3-r1..r10 in scope, p3-r11 out of scope (phase 3)

Reviewer a9217b89215b69c05 (Opus 5.5). Held up: emits-literal sections, template allowed-sections + step ids + resume, blocked->failed, plan:ticks completes the phase, verbs committing per §5.C.6, test changes moved not weakened, 4.22.0 lockstep. Blockers: p3-r1, p3-r2 (bypasses), p3-r3 (atomicity).

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-09-25T23:47:57 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: Record path accepts answered_by: operator on an out-of-scope fix without transcript verification

verify_operator_claim moved to fr.journal.operator; the engine runs it in _journal_writes for every resolution claiming answered_by operator (record + verb paths); before_write hook removed. test_record_review_fixes::test_a_record_fixing_an_out_of_scope_finding_as_operator_is_verified.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-09-25T23:47:57 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: Plain resolve --step deliver --state done bypasses the live PR-section check

_deliver_pr_gate in _resolve_body (step emits pr, state done, before _complete_step) renders pr-body.md and checks live missing_sections; engine pre-check removed. 15 deliver/pr-emitting tests now serve a complying PR via the complete_live_pr fixture. test_the_flag_form_deliver_is_refused_without_the_out_of_scope_section.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-09-25T23:47:58 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: Invalid-record atomicity: crash window, retry wedges on existing ids, restore misses cursor/usage paths and can revert committed files

Record removed only after all writes+gates (tracked: just before the commit that records it); identical re-applied journal entries/resolutions/rows are no-ops so a retry heals; ResolveGuard remembers cursor/usage/spec-journal/PR-render bytes before writing; no restore once a commit landed. Crash/heal/changed-entry/post-commit-raise tests in test_record_review_fixes.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-09-25T23:47:59 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: --record silently ignores --no-questions/--reason/--answered-by/--agent/--harness/--model

Both: --record refuses --no-questions/--reason/--answered-by/--agent/--harness/--model; record gains no_questions + reason (outcome section) so the brainstorm bypass stays one --record resolve; fr-goal §1 documents it. Tests: flag refusal (5 cases) + brainstorm no_questions record.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-09-25T23:48:00 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: Record acceptance entries create-or-move by id existence, losing add/set-status refusals

capability/acceptance present = create-only (existing id refused unless identical, for retry); absent = move-only (unknown id refused). Two tests in test_record_verbs.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-09-25T23:48:00 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: fr-goal SKILL.md:96 claims record-path answered_by verification that does not exist

SKILL.md:96 claim now true via p3-r1 (engine verifies answered_by operator on the record path); re-read, wording kept; §1 now names the record spelling evidence: {answered_by: operator}.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-09-25T23:48:01 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: No test that deliver's tests= log gate still fires through --record

test_deliver_tests_log_gate_fires_through_a_record[absent|stale]: exit 2, no byte or HEAD change, deliver still running.

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved created=2026-09-25T23:48:02 state=fixed resolves=p3-r8 -->
### p3-r8-resolved · finding [fixed] · resolves p3-r8: fr plan edit --complete-phase no longer enforces the refactor check

_plan_writes runs refactor_gaps on every actual phase completion (verb or record), counting the record in-memory refactor/journal entries; back-compat journal no-refactor-because still satisfies it. test_complete_phase_verb_refuses_a_task_with_no_refactor_reason; prose in fr-execute + fr-phase-executor notes it.

<!-- fr:journal kind=finding scope=plan id=p3-r9-resolved created=2026-09-25T23:48:02 state=fixed resolves=p3-r9 -->
### p3-r9-resolved · finding [fixed] · resolves p3-r9: --record deletes and commits any parseable path; relative path resolved against cwd

--record resolved against the repo root and required under records_dir(run); otherwise exit 2, nothing touched. Tests: outside-dir refusal + relative path from another cwd.

<!-- fr:journal kind=finding scope=plan id=p3-r10-resolved created=2026-09-25T23:48:03 state=fixed resolves=p3-r10 -->
### p3-r10-resolved · finding [fixed] · resolves p3-r10: Successful resolve prints a second stderr line (fr: committed …)

commit_records(quiet=True) from the engine resolve drops the fr: committed echo (a refused commit still reports). test_a_successful_resolve_prints_one_line_on_stdout_and_stderr_together.

<!-- fr:journal kind=finding scope=plan id=d-oos-cov-rsync created=2026-09-26T00:09:53 state=open review_scope=out -->
### d-oos-cov-rsync · finding [open] (reviewer: out of scope) · Local full suite with coverage races install.sh's rsync of the repo root (.coverage.* vanish, rsync exit 23)

Seen twice at deliver on macOS under pytest -n auto with coverage: test_install_sh TestInstallRules (test_installs_rule_file, test_idempotent). Passes alone and with --no-cov; CI (Linux) green on every push. Fix: exclude .coverage* from the rsync, or point COVERAGE_FILE outside the repo.

<!-- fr:journal kind=finding scope=plan id=d-oos-cov-rsync-resolved created=2026-09-26T00:09:54 state=open resolves=d-oos-cov-rsync out_of_scope=true -->
### d-oos-cov-rsync-resolved · finding [out-of-scope] · resolves d-oos-cov-rsync: Local full suite with coverage races install.sh's rsync of the repo root (.coverage.* vanish, rsync exit 23)

Not caused by this change: install.sh and coverage config are unchanged here; the race needs xdist+coverage, which #615 introduced.

<!-- fr:journal kind=finding scope=plan id=d-oos-tests-window created=2026-09-26T00:09:54 state=open review_scope=out -->
### d-oos-tests-window · finding [open] (reviewer: out of scope) · deliver's tests= gate cannot see a run_in_background suite (call window ends at launch)

run_cmd.py _verify_tests_log: orchestrator_wrote_since windows are the Bash call's start..end; a backgrounded call ends immediately, so the log's mtime minutes later is outside it — contradicting the brief's long_commands rule that tells you to background long suites. Workaround used: foreground with a long timeout.

<!-- fr:journal kind=finding scope=plan id=d-oos-tests-window-resolved created=2026-09-26T00:09:55 state=open resolves=d-oos-tests-window out_of_scope=true -->
### d-oos-tests-window-resolved · finding [out-of-scope] · resolves d-oos-tests-window: deliver's tests= gate cannot see a run_in_background suite (call window ends at launch)

Pre-existing gate behaviour (not introduced by this branch); found while delivering it.

<!-- fr:journal kind=finding scope=plan id=d-oos-cli-gate-unobserved created=2026-09-26T00:09:56 state=open review_scope=out -->
### d-oos-cli-gate-unobserved · finding [open] (reviewer: out of scope) · An operator gate on a kind: cli step never persists unobserved to the cursor

Recorded as discovery p2-d-review-fixes during phase-2 fixes: the step has no unit to hold evidence; stderr notice only. kind: agent gates (fr-goal brainstorm) do record it.

<!-- fr:journal kind=finding scope=plan id=d-oos-cli-gate-unobserved-resolved created=2026-09-26T00:09:56 state=open resolves=d-oos-cli-gate-unobserved out_of_scope=true -->
### d-oos-cli-gate-unobserved-resolved · finding [out-of-scope] · resolves d-oos-cli-gate-unobserved: An operator gate on a kind: cli step never persists unobserved to the cursor

Predates this change; this branch added unobserved for agent-step gates only.

<!-- fr:journal kind=finding scope=plan id=p3-r11-resolved-2 created=2026-09-26T00:15:31 state=open resolves=p3-r11 tracked_by=#629 -->
### p3-r11-resolved-2 · finding [deferred → #629] · resolves p3-r11: test_opencode_plugin_live flaky under parallel load

Operator asked to file it; tracked.

<!-- fr:journal kind=finding scope=plan id=d-oos-cov-rsync-resolved-2 created=2026-09-26T00:15:40 state=open resolves=d-oos-cov-rsync tracked_by=#630 -->
### d-oos-cov-rsync-resolved-2 · finding [deferred → #630] · resolves d-oos-cov-rsync: Local full suite with coverage races install.sh's rsync of the repo root (.coverage.* vanish, rsync exit 23)

Operator asked to file it; tracked.

<!-- fr:journal kind=finding scope=plan id=d-oos-tests-window-resolved-2 created=2026-09-26T00:15:40 state=open resolves=d-oos-tests-window tracked_by=#631 -->
### d-oos-tests-window-resolved-2 · finding [deferred → #631] · resolves d-oos-tests-window: deliver's tests= gate cannot see a run_in_background suite (call window ends at launch)

Operator asked to file it; tracked.

<!-- fr:journal kind=finding scope=plan id=d-oos-cli-gate-unobserved-resolved-2 created=2026-09-26T00:15:41 state=open resolves=d-oos-cli-gate-unobserved tracked_by=#632 -->
### d-oos-cli-gate-unobserved-resolved-2 · finding [deferred → #632] · resolves d-oos-cli-gate-unobserved: An operator gate on a kind: cli step never persists unobserved to the cursor

Operator asked to file it; tracked.
