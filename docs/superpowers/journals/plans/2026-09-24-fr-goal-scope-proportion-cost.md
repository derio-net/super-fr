# Journal: 2026-09-24-fr-goal-scope-proportion-cost

<!-- fr:journal kind=discovery scope=plan id=8d08750145d7 created=2026-09-24T20:54:01 phase=3 -->
### 8d08750145d7 · discovery · no-refactor-because P3.T3 (phase 3)

Two tuple entries in run_cmd.py plus one manifest key in two identical files; no structure to refactor.

<!-- fr:journal kind=discovery scope=plan id=e3399d6b9c1e created=2026-09-24T20:54:02 phase=4 -->
### e3399d6b9c1e · discovery · no-refactor-because P4.T2 (phase 4)

An agent prose file, manifest keys, a parity row, install wiring and generated mirrors; no code structure to refactor.

<!-- fr:journal kind=discovery scope=plan id=949087891321 created=2026-09-24T20:54:02 phase=4 -->
### 949087891321 · discovery · no-refactor-because P4.T3 (phase 4)

Skill prose, explainer re-render and a version bump; no code.

<!-- fr:journal kind=decision scope=plan id=d-p1-v6-guard created=2026-09-24T21:01:15 phase=1 -->
### d-p1-v6-guard · decision · 5->6 guard asks run_unit_record.is_unit_record_body, not cursor_guard (phase 1)

cursor_guard reads with the frozen v4 model, which rejects units, so it cannot certify a v5 cursor. The live-parser tripwire (test_no_run_migration_names_the_live_parser) allows the live model only in run_unit_record.py, so the 5->6 hop routes its readability check through a new public is_unit_record_body there instead of widening the tripwire. Sound only while changes stay additive; the first field removal must freeze RunStateV5 and repoint it.

<!-- fr:journal kind=discovery scope=plan id=x-p1-v5-fixture created=2026-09-24T21:01:15 phase=1 -->
### x-p1-v5-fixture · discovery · captured a v5 run cursor fixture (phase 1)

tests/fixtures/run_cursors/v5/2026-09-23-fix-457-uninstall-rules.yaml captured byte-for-byte with git show from the archived run at 7dbdc35b; NOTE.md row with sha256 added; population assertions in test_run_cursor_fixtures and test_migration_runner extended to v5 so the parametrised every-cursor-migrates-to-current test exercises the 5->6 hop on a real file.

<!-- fr:journal kind=decision scope=plan id=d-p1-dedupe-then-window created=2026-09-24T21:08:50 phase=1 -->
### d-p1-dedupe-then-window · decision · main-session reader dedupes before windowing (phase 1)

A message's content-block records can straddle a step boundary by milliseconds; deduplicating by message.id first and windowing second charges it once, to the step its first record fell in. Windowing first would count it in both adjacent steps.

<!-- fr:journal kind=decision scope=plan id=v-p1-measure-step created=2026-09-24T21:08:59 phase=1 -->
### v-p1-measure-step · decision · DEVIATION: Protocol method is measure_step(env, sessions, start, end, directories); measure_main_session stays per-reader (phase 1)

Plan P1.T3.S2 said add measure_main_session to the TranscriptReader Protocol. The two readers take different inputs (a Claude transcript path vs an OpenCode DB + session id), and OpenCode's candidate fallback (unique top-level session by directory) is reader-specific, so the Protocol gained measure_step(env, sessions, start, end, directories) -> MainSessionUsage|None and each reader keeps its own per-session measure_main_session. candidate_sessions also takes harness= (default claude-code): attempt sessions and current_session are Claude ids, and bindings are filtered by harness (unknown counts as Claude Code), so an OpenCode binding never makes a Claude measurement 'unreadable'. Also: test_run_legacy / test_run_v4_to_v5 fixture globs narrowed to v[1-4] now that v5/ exists.

<!-- fr:journal kind=discovery scope=plan id=x-p1-opencode-schema created=2026-09-24T21:12:26 phase=1 -->
### x-p1-opencode-schema · discovery · OpenCode DB shape verified live (read-only) (phase 1)

sqlite3 -readonly on ~/.local/share/opencode/opencode.db (2026-09-24): session(id, parent_id, directory, ...), message(id, session_id, time_created INTEGER epoch MILLISECONDS, data TEXT). An assistant row's data keys: agent, cost, finish, mode, modelID, parentID, providerID, role, time{created,completed} (ms), tokens{total,input,output,reasoning,cache{read,write}}. No content or identity copied. The reader windows on time_created/1000 (second precision, same rule as Claude Code), opens the DB with a mode=ro URI, and tests use a fixture DB with that schema subset; conftest now points FR_OPENCODE_DB at a nonexistent path suite-wide.

<!-- fr:journal kind=decision scope=plan id=d-p1-overcount-rule created=2026-09-24T21:23:32 phase=1 -->
### d-p1-overcount-rule · decision · 'possibly over-counted' is dated by the run's first main_session (phase 1)

No field records which fr measured an attempt, and adding one would be another shape change. The dedupe ships in the same release as main-session measurement, so fr.run.cost.possibly_over_counted flags every measured attempt that returned before the run's earliest main_session-bearing step's at (all of them when no step carries main_session). Conservative by design: a run whose main session was unmeasurable flags every measurement. The pure builder (cost_rows / subagent_total / possibly_over_counted) was written with the command in S2, so S3's refactor had nothing left to extract.

<!-- fr:journal kind=finding scope=plan id=p1-f1 created=2026-09-24T21:28:34 phase=1 state=open -->
### p1-f1 · finding [open] · fr-goal-main-session-cost flipped to ci before the live cross-harness check (plan P4.T3.S3 keeps it skipped) (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-f1-resolved created=2026-09-24T21:28:36 phase=1 state=fixed resolves=p1-f1 -->
### p1-f1-resolved · finding [fixed] · resolves p1-f1: fr-goal-main-session-cost flipped to ci before the live cross-harness check (plan P4.T3.S3 keeps it skipped) (phase 1)

Row moved back to skipped via fr acceptance set-status; the ci flip waits on the live check.

<!-- fr:journal kind=review scope=plan id=r-p1 created=2026-09-24T21:28:36 phase=1 -->
### r-p1 · review · Phase 1 review (independent reviewer): 1 finding (p1-f1, fixed); 6 deviations accepted (phase 1)

Reviewer: dispatched code-reviewer subagent a1ea2343c237b8a52. Deviations 1-5 accepted with reasons; deviation 6 = p1-f1.

<!-- fr:journal kind=discovery scope=plan id=x-p2-journal-stamp-tz created=2026-09-24T21:40:38 phase=2 -->
### x-p2-journal-stamp-tz · discovery · journal created stamps are naive LOCAL time; operator_answered_since reads naive as UTC (phase 2)

fr journal's _timestamp() is datetime.now() with no offset (local wall clock), while fr.run.telemetry.parse_timestamp treats a naive stamp as UTC. Passing an out-of-scope record's created straight into operator_answered_since would open the question window hours late east of UTC (the operator's machine is +02:00) and refuse an operator who answered in between. Added journal_stamp_as_utc (naive -> local -> UTC), pinned by a TZ=Europe/Athens test.

<!-- fr:journal kind=decision scope=plan id=d-p2-guard-shape created=2026-09-24T21:40:39 phase=2 -->
### d-p2-guard-shape · decision · operator guard: writes succeed, the fold refuses; a later operator record cures (phase 2)

Per P2.T3.S1(a) a fixed record without answered_by=operator is WRITTEN by both resolve and add --resolves, and fr journal check / the review-phase witness then report an unauthorized fix. The one command-side refusal is the Claude Code verification of an --answered-by operator CLAIM (observed False -> exit 2, nothing written). Since the journal is append-only, the cure is a later fixed record with answered_by=operator (ratifies) or any record moving the finding off fixed (clears); the fold tracks that per finding. Unknown answered_by / review_scope token values parse as absent (never fatal; for answered_by that is the fail-closed direction). The verification window opens at the finding's LAST out-of-scope record, else the finding's own created. Advisory notice text comes from the parity row's scope_note, like the brainstorm gate.

<!-- fr:journal kind=decision scope=plan id=v-p2-render-shape created=2026-09-24T21:40:39 phase=2 -->
### v-p2-render-shape · decision · DEVIATION (scope note): render marks reclassification as a blockquote; deliver's both-journal render left to phase 4 (phase 2)

Reviewer tag renders in the heading as '(reviewer: in scope|out of scope)'; out-of-scope findings and their records move under '## Out-of-scope findings'; a review_scope=in finding ending out-of-scope gets '> reclassified by the orchestrator — the reviewer tagged this in scope' under its heading. Task 2's title mentions 'both scopes at deliver' but none of its steps do; spec §A's deliver change is a manifest/skill edit that 04.yaml (SKILL §8 renders both journals) already owns, so nothing for it was done here.

<!-- fr:journal kind=finding scope=plan id=p2-f1 created=2026-09-24T21:56:45 phase=2 state=open review_scope=in -->
### p2-f1 · finding [open] (reviewer: in scope) · out-of-scope -> deferred -> fixed interleaving is designed behaviour but unpinned by a test (phase 2)
