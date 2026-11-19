<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-run-durability

<!-- fr:journal kind=repro scope=debug id=b0abf3ab05f1 created=2026-11-19T11:39:00+00:00 -->
### b0abf3ab05f1 · repro · Four run-durability defects, all live on origin/main 15990c10

save_run_state (run/model.py:600) and 14 plan_ops.py writes use Path.write_text, which truncates before it writes: an exception or crash mid-write leaves a truncated cursor/plan/spec (#1500, #1524). No lock or compare-before-write guards a cursor: two fr run commands that load the same cursor each save, and the later save drops the earlier one's update (#1511). A kind: cli step runs subprocess.run(shell=True) with no timeout and stores its whole stdout in the cursor (run_cmd.py:6498, #1507).
