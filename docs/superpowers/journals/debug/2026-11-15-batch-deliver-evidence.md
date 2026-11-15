<!-- fr:journal-schema=4 -->
# Journal: 2026-11-15-batch-deliver-evidence

<!-- fr:journal kind=decision scope=debug id=ad1b1adc37b9 created=2026-11-15T16:52:31+00:00 decided_by=operator -->
### ad1b1adc37b9 · decision · Four independent root causes, fixed as one PR

Investigation found four separate causes in four code sites, sharing only a theme (a witness that passes or fails falsely). The brief said to stop and ask on more than one root cause; the operator chose to fix all four in one PR.

<!-- fr:journal kind=root-cause scope=debug id=rc-1454 created=2026-11-15T16:52:33+00:00 -->
### rc-1454 · root-cause · #1454: a fresh deliver tests log names no code tree

`_verify_tests_log` (run_cmd.py) checks the log's writer and time window only; `_local_stamp_witness` then stamps HEAD's code tree. A commit after the suite and before deliver leaves the tree clean, so the log is accepted as covering HEAD and a local row is stamped with a tree the suite never ran. Phase logs already guard this with `newest_code_mtime` (freshness against every code path since the merge-base).
