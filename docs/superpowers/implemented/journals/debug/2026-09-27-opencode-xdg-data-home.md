# Journal: 2026-09-27-opencode-xdg-data-home

<!-- fr:journal kind=repro scope=debug id=574cbe9b791a created=2026-09-27T19:27:44+00:00 -->
### 574cbe9b791a · repro · XDG_DATA_HOME-set OpenCode run: deliver refuses a valid suite log

gh#740. With XDG_DATA_HOME set and FR_OPENCODE_DB unset, OpenCode writes sessions to $XDG_DATA_HOME/opencode/opencode.db, but OpenCodeReader.database() resolves ~/.local/share/opencode/opencode.db. _opencode_wrote_since opens that (readable, wrong) db, finds no matching top-level bash part, returns [] and deliver refuses: 'no command of YOURS wrote it'. Repro in unit form: OpenCodeReader().database({'XDG_DATA_HOME': d}) != d/opencode/opencode.db; and orchestrator_wrote_since over a db with no part since the unit opened returns [] instead of None.

<!-- fr:journal kind=root-cause scope=debug id=03d72098df81 created=2026-09-27T19:27:45+00:00 -->
### 03d72098df81 · root-cause · Reader ignores XDG_DATA_HOME, and a readable-but-irrelevant db is read as 'no writer'

One root, two faces. (1) telemetry.py OpenCodeReader.database knows only FR_OPENCODE_DB and $HOME/.local/share — OpenCode (xdg-basedir) uses $XDG_DATA_HOME when set and non-empty. (2) _opencode_wrote_since collapses 'this db never saw the run' into [] (observed: nobody wrote the log). A db recording no part at all since the unit opened cannot hold the calling orchestrator (its own resolve call is a part), so the honest answer is None (unobservable -> freshness fallback). Activity is measured on part.time_updated, not session.time_updated, per the earlier review that forbade trusting the session row.

<!-- fr:journal kind=finding scope=debug id=f-xdg created=2026-09-27T19:40:24+00:00 state=fixed -->
### f-xdg · finding [fixed] · Reader follows XDG_DATA_HOME; a db with no part since the unit opened is None

telemetry.py: OpenCodeReader.database = FR_OPENCODE_DB > XDG_DATA_HOME/opencode/opencode.db (set, non-empty) > ~/.local/share. _opencode_wrote_since checks EXISTS(part.time_updated >= since) before reading windows; none -> None. Pinned first-failing by test_run_opencode_reader.py::test_the_database_path_follows_xdg_data_home_as_opencode_does, test_run_tests_log_opencode.py::test_a_database_that_saw_nothing_since_the_unit_opened_is_unobservable, ::test_on_opencode_the_suite_log_is_found_under_xdg_data_home, ::test_on_opencode_a_database_without_the_run_does_not_refuse_the_log. Full suite: 6694 passed. Not done here: naming the database in run_cmd.py's warnings (issue part 3) — the batch fenced run_cmd.py off.

<!-- fr:journal kind=review scope=debug id=ddd5dd9dc9b2 created=2026-09-27T19:47:00+00:00 -->
### ddd5dd9dc9b2 · review · Independent adversarial review: no findings above threshold

Separate-context reviewer traced the #638 bypass question (the active gate counts any part, so an edit-tool-composed log still yields [] via the unchanged top-level bash filter), child-session activity, the #638 fixture correction (was passing by accident on a stale fixed stamp), and source_of. Two sub-threshold notes, both left as-is: (a) relative XDG_DATA_HOME is not rejected — deliberately, OpenCode's xdg-basedir does not reject it either, so matching it keeps fr on the db OpenCode writes; (b) the None gate assumes OpenCode persists an in-flight bash part — if not, the effect is the existing unobserved+warning fallback, never a silent accept.
