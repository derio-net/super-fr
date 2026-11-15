<!-- fr:journal-schema=4 -->
# Journal: 2026-11-15-batch-deliver-evidence

<!-- fr:journal kind=decision scope=debug id=ad1b1adc37b9 created=2026-11-15T16:52:31+00:00 decided_by=operator -->
### ad1b1adc37b9 · decision · Four independent root causes, fixed as one PR

Investigation found four separate causes in four code sites, sharing only a theme (a witness that passes or fails falsely). The brief said to stop and ask on more than one root cause; the operator chose to fix all four in one PR.

<!-- fr:journal kind=root-cause scope=debug id=rc-1454 created=2026-11-15T16:52:33+00:00 -->
### rc-1454 · root-cause · #1454: a fresh deliver tests log names no code tree

`_verify_tests_log` (run_cmd.py) checks the log's writer and time window only; `_local_stamp_witness` then stamps HEAD's code tree. A commit after the suite and before deliver leaves the tree clean, so the log is accepted as covering HEAD and a local row is stamped with a tree the suite never ran. Phase logs already guard this with `newest_code_mtime` (freshness against every code path since the merge-base).

<!-- fr:journal kind=root-cause scope=debug id=rc-1395 created=2026-11-15T16:52:34+00:00 -->
### rc-1395 · root-cause · #1395: verify_ci forge reads raise GhError past _ci_tests_witness

`verify_ci` calls `open_pr_for_head`, `pr_view`, `required_check_names` and `commit_checks` with no GhError handling; `_ci_tests_witness` catches only CiPending and CiEvidenceRefused, so a network failure escapes as a traceback with exit 1 (fr-goal reads 1 as 'record applied, a chained step failed').

<!-- fr:journal kind=root-cause scope=debug id=rc-1303 created=2026-11-15T16:52:36+00:00 -->
### rc-1303 · root-cause · #1303: _program takes a process wrapper as the program

`fr.run.telemetry._program` steps over assignments, `uv run fr`, `fr isolation exec --` and `bash/sh -c` only; `timeout`, `nice`, `nohup`, `env`, `time`, `stdbuf` and `caffeinate` become the command word, so a capture script run behind one is never witnessed and the refusal names no cause.

<!-- fr:journal kind=root-cause scope=debug id=rc-1462 created=2026-11-15T16:52:37+00:00 -->
### rc-1462 · root-cause · #1462: deliver stamps a merged local row in place

`_local_stamp_plan` → `stamp_local` rewrites the row block for every local row of the feature's fragment, merged on the default ref or not. The fold keeps the merged definition (row still unstamped) and `fr acceptance check` fails 'edited in place', while deliver exits 0. A merged row changes only by an amendment (R16).

<!-- fr:journal kind=finding scope=debug id=fix-1303 created=2026-11-15T17:02:34+00:00 state=fixed -->
### fix-1303 · finding [fixed] · #1303 fixed: process wrappers are stepped over; the refusal names the hiding word

telemetry._unwrap steps over timeout/nice/nohup/env/time/stdbuf/caffeinate (per-wrapper option grammar, no recursion depth spent); near_miss_program feeds visual's refusal ('fr read its program as `xargs`'). Pinned by test_run_telemetry_visual.py::test_a_process_wrapper_before_the_program_is_stepped_over (22 forms), ::test_the_near_miss_names_the_command_word_that_hid_the_script, and test_run_evidence_visual.py::test_the_refusal_names_the_word_that_hid_the_script / ::test_a_capture_script_behind_timeout_is_witnessed.

<!-- fr:journal kind=finding scope=debug id=fix-1395 created=2026-11-15T17:03:48+00:00 state=fixed -->
### fix-1395 · finding [fixed] · #1395 fixed: a forge read failure in tests: ci exits 75 in one line

_ci_tests_witness catches the forge CLI errors (GhError, GlabError, TeaError) and exits CI_PENDING_EXIT ('could not read CI from the forge (...). Nothing was recorded: resolve again.'); HostRefusedError exits 2. Pinned by test_run_resolve_tests_ci.py::test_a_failed_forge_read_exits_75_naming_it_and_applies_nothing (3 errors) and ::test_a_host_trust_refusal_is_no_retry_and_exits_2.

<!-- fr:journal kind=hypothesis scope=debug id=h-1454-mtime created=2026-11-15T17:10:33+00:00 -->
### h-1454-mtime · hypothesis · #1454: bind the fresh log by mtime freshness, not by recording a tree in the witness

Recording code_tree in the fresh deliver witness (the issue's suggestion) changes the cursor's evidence shape (a run-kind stamp bump + migration) and still needs the tree at the moment the suite STARTED, which fr cannot see. The phase path's newest_code_mtime rule answers the same question with no shape change: the edit behind a post-suite commit is newer than the log. Chosen.
