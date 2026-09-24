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
