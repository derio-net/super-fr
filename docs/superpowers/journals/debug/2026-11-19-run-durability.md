<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-run-durability

<!-- fr:journal kind=repro scope=debug id=b0abf3ab05f1 created=2026-11-19T11:39:00+00:00 -->
### b0abf3ab05f1 · repro · Four run-durability defects, all live on origin/main 15990c10

save_run_state (run/model.py:600) and 14 plan_ops.py writes use Path.write_text, which truncates before it writes: an exception or crash mid-write leaves a truncated cursor/plan/spec (#1500, #1524). No lock or compare-before-write guards a cursor: two fr run commands that load the same cursor each save, and the later save drops the earlier one's update (#1511). A kind: cli step runs subprocess.run(shell=True) with no timeout and stores its whole stdout in the cursor (run_cmd.py:6498, #1507).

<!-- fr:journal kind=root-cause scope=debug id=1cce6c5a4d8f created=2026-11-19T11:39:08+00:00 -->
### 1cce6c5a4d8f · root-cause · Three causes, not one: non-atomic writes; no cursor concurrency control; an unbounded cli step

(1) Writers bypass fr.artifacts.atomic.write_text_atomic. (2) The cursor's load-modify-save has no mutual exclusion; atomicity alone does not prevent a lost update. (3) The cli step executor sets no timeout and stores proc.stdout unbounded. Fixed as one commit each, failing test first.

<!-- fr:journal kind=finding scope=debug id=f-atomic created=2026-11-19T21:11:59+00:00 state=fixed -->
### f-atomic · finding [fixed] · Cursor, plan and spec writes are atomic (#1500, #1524)

save_run_state and all 14 plan_ops.py writes go through write_text_atomic (temp file in the same directory, fsync, os.replace). A failed fsync leaves the old file byte-identical and no temp file behind (tests/unit/test_run_durability.py section 1; an AST tripwire forbids plain write_text in both modules). write_text_atomic now gives a new file the umask default mode, as write_text did, instead of mkstemp's 0600. Commit 1bc4281aa.

<!-- fr:journal kind=finding scope=debug id=f-lost-update created=2026-11-19T21:12:01+00:00 state=fixed -->
### f-lost-update · finding [fixed] · A save that would lose another command's cursor update refuses (#1511)

run/model.py records the sha256 of the cursor bytes each command read or wrote. save_run_state compares the file on disk with that record, under a flock on the runs directory, and raises RunStateConflictError when it changed or was removed; fr run exits 2 and writes nothing, fr pr create reports the opened PR it could not record. The record is cleared at each CLI entry, so one command saving twice is fine. A long-held per-command lock was rejected: resolve_in_process re-enters within one process, and flock belongs to the open file description. Commit 0d242ad63.

<!-- fr:journal kind=finding scope=debug id=f-cli-bound created=2026-11-19T21:12:03+00:00 state=fixed -->
### f-cli-bound · finding [fixed] · A cli step is bounded in time and in stored output (#1507)

The cli executor runs the shell in its own session with a timeout (FR_CLI_STEP_TIMEOUT, default 600 s, 0 for none; a malformed value exits 2 and runs nothing). On timeout os.killpg kills the whole group (killing only the shell left 'sleep 30 | cat' holding the pipe open) and the step fails with exit 124. The cursor stores the last 16 KiB of stdout under a 'truncated' header. Commit fdcf46fb6.
