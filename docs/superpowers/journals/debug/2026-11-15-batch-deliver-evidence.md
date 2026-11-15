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
