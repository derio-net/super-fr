<!-- fr:journal-schema=4 -->
# Journal: 2026-11-15-batch-gate-truth

<!-- fr:journal kind=root-cause scope=debug id=ff687e37c98b created=2026-11-15T11:06:11+00:00 -->
### ff687e37c98b · root-cause · 1399: ledger _run_text lists only RUNS_DIR

triage/ledger.py _run_text reads docs/superpowers/runs only; fr archive moves the cursor to implemented/runs, so gated_rows_at returns NO_RUN.

<!-- fr:journal kind=root-cause scope=debug id=47f69cbf4e60 created=2026-11-15T11:06:13+00:00 -->
### 47f69cbf4e60 · root-cause · 1389: gate pass --yes exits 0 on a failed tracker close

commands/gate_cmd.py: the pass path prints the retry line when report.errors and returns normally; the already-passed branch and backfill exit 1.

<!-- fr:journal kind=root-cause scope=debug id=b9082aeb2326 created=2026-11-15T11:06:15+00:00 -->
### b9082aeb2326 · root-cause · 1293: apply_phase skips a live-DONE op without recording it

ops/gate.py apply_phase skips when _closed() is not None; for a check-closed op that reads only the live status row, so fr ops apply (which records done, R7) never runs. holds.devops_blockers then reports never checked and refuses fr gate pass at stage 6: it blocks, not only mislabels.

<!-- fr:journal kind=root-cause scope=debug id=cfd4ca72d002 created=2026-11-15T11:06:17+00:00 -->
### cfd4ca72d002 · root-cause · 1275: stage_7 keeps gate:tester; devops_brief ignores the gate record

ops/gate.py stage_7 records no tester step remains and leaves the label; run/closeout.py devops_brief checks only that deliver is done. Where deliver applies gate:tester for a devops-only spec is not yet traced.

<!-- fr:journal kind=finding scope=debug id=9496e9c666dd created=2026-11-15T17:13:20+00:00 state=fixed -->
### 9496e9c666dd · finding [fixed] · 1399 fixed: ledger reads archived runs

_run_text lists RUNS_DIR and ARCHIVED_RUNS_DIR. Test first: test_triage_exit_gates_drive.py::test_gh1399_an_archived_run_keeps_its_gated_rows (failed: rows == ()).

<!-- fr:journal kind=finding scope=debug id=e014176e2658 created=2026-11-15T17:13:23+00:00 state=fixed -->
### e014176e2658 · finding [fixed] · 1389 fixed: gate pass --yes exits 1 on a failed close

The pass stands; the command exits 1 after the retry line. test_gate_cmd.py::test_a_tracker_failure_never_reverses_the_pass_but_exits_1 (it previously pinned exit 0).

<!-- fr:journal kind=finding scope=debug id=207a3e6f6aba created=2026-11-15T17:13:25+00:00 state=fixed -->
### 207a3e6f6aba · finding [fixed] · 1293 fixed: apply_phase records a live-DONE op

Skip only when the closure is already recorded on the ops branch (_recorded_here); otherwise fr ops apply --yes records it (R7) and runs nothing. test_ops_gate.py::test_gh1293_an_op_already_done_live_is_recorded_not_skipped.
