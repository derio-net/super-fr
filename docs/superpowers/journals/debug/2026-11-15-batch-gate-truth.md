<!-- fr:journal-schema=4 -->
# Journal: 2026-11-15-batch-gate-truth

<!-- fr:journal kind=root-cause scope=debug id=ff687e37c98b created=2026-11-15T11:06:11+00:00 -->
### ff687e37c98b · root-cause · 1399: ledger _run_text lists only RUNS_DIR

triage/ledger.py _run_text reads docs/superpowers/runs only; fr archive moves the cursor to implemented/runs, so gated_rows_at returns NO_RUN.
