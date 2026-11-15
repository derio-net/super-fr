<!-- fr:journal-schema=4 -->
# Journal: 2026-11-15-batch-gate-truth

<!-- fr:journal kind=root-cause scope=debug id=ff687e37c98b created=2026-11-15T11:06:11+00:00 -->
### ff687e37c98b · root-cause · 1399: ledger _run_text lists only RUNS_DIR

triage/ledger.py _run_text reads docs/superpowers/runs only; fr archive moves the cursor to implemented/runs, so gated_rows_at returns NO_RUN.

<!-- fr:journal kind=root-cause scope=debug id=47f69cbf4e60 created=2026-11-15T11:06:13+00:00 -->
### 47f69cbf4e60 · root-cause · 1389: gate pass --yes exits 0 on a failed tracker close

commands/gate_cmd.py: the pass path prints the retry line when report.errors and returns normally; the already-passed branch and backfill exit 1.
