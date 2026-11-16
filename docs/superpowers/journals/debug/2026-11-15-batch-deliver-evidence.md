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

<!-- fr:journal kind=finding scope=debug id=fix-1454 created=2026-11-15T17:10:34+00:00 state=fixed -->
### fix-1454 · finding [fixed] · #1454 fixed: deliver refuses a fresh log older than any code path

_verify_tests_log → _refuse_stale_suite_log (newest_code_mtime since default_merge_base, the log itself ignored). Pinned by test_deliver_local_stamp.py::test_a_fresh_log_older_than_a_committed_code_change_is_refused and ::test_a_fresh_log_written_after_the_last_code_change_is_accepted; three existing tests that changed the tree after writing their log now mark the suite as run last (_suite_ran_last).

<!-- fr:journal kind=finding scope=debug id=fix-1462 created=2026-11-15T17:19:18+00:00 state=fixed -->
### fix-1462 · finding [fixed] · #1462 fixed: a merged local row is stamped by a new set-status amendment

_local_stamp_plan → local_stamp_target picks the block; frozen() (merged_row_ids for a row block, membership in the fold's pending for an amendment) routes a merged one to append_amendment(SetStatus(..., status=local, local=stamp)). _feature_local_ids now counts the feature's own merged rows re-set by its amendments. Pinned by test_deliver_local_stamp.py::test_a_merged_local_row_is_stamped_by_an_amendment[slug|slug-design] (the issue's reproduction) and ::test_a_merged_set_status_amendment_is_not_rewritten; ::test_a_pending_set_status_amendment_is_stamped_in_place still holds.

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-11-15T20:01:31+00:00 -->
### review-1 · review · Verification and CI review: three findings, all fixed in the branch

Raised by the full suite and CI on 920ff5c60, after the four fixes:

1. The forge-backend deliver fixtures (test_deliver_pr_body_forges.py, 3 tests) wrote suite.log before committing .devcontainer/fr-profiles.yaml; the #1454 guard rightly refused them. Fixed in the fixtures (record_support.suite_ran_last, shared with test_deliver_local_stamp.py), not the guard.
2. test_tripwire_forge_adapter: the #1395 handler imported fr.gh in run_cmd. Fixed by catching fr.hostclient.FORGE_ERRORS (same three errors, through the adapter).
3. test_run_telemetry::test_a_backgrounded_suite_passes_the_deliver_gate_end_to_end drove _verify_tests_log from a non-git directory; the #1454 guard fails closed there (GitUnavailableError). Kept fail-closed; the test now runs in a git checkout tracking no code.

No other failures across both Python versions' 7 shards. ruff, mypy, fr docs check and the change-fragment gate are clean.
