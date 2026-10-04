# Journal: 2026-10-04-drive-forge-resilience

<!-- fr:journal kind=repro scope=debug id=82958a6fae6b created=2026-10-04T04:26:44+00:00 -->
### 82958a6fae6b · repro · A stalled forge read hangs the drive loop; its failure then ends it (exit 2)

Live (wave-driver Test Plan 16, 2026-10-03, GitHub API degradation): the per-pass re-collect's `gh issue list --limit 1000` stalled ~16 min, then failed with `Post .../graphql: unexpected EOF`; `fr triage batch drive` (loop mode) printed `error: ...` and exited 2. A ready, green PR sat unmerged throughout. Repro in tests: (a) `fr.gh._run_gh` against a `gh` that never returns blocks forever; (b) make the drive's re-collect raise `ForgeError` on one pass in loop mode → exit 2 instead of a retry after --interval.

<!-- fr:journal kind=root-cause scope=debug id=18c656e97ae7 created=2026-10-04T04:26:44+00:00 -->
### 18c656e97ae7 · root-cause · The driver assumes forge reads always return: they are unbounded and a failed one is fatal

One missing contract, two places it shows. (1) `fr.gh._run_gh` — the one funnel every gh read behind `collect` (`GhForge`) and the driver's adapter reads (`RealGhClient`) goes through — calls `subprocess.run` with no `timeout`, so a stalled `gh` blocks the pass indefinitely. (2) In `triage_batch_cmd`, `recollect` turns a `ForgeError` into `_fail` (exit 2) and `_Driver.snapshot` turns any `FORGE_ERRORS` into `_fail(code=1)`, with no loop-mode distinction — unlike a refused merge, which R7/rg-4 already report once and retry next pass. Bounding the read (1) only converts a hang into a failure; (2) is what lets the loop survive that failure. The issues (#909 → #910) specify exactly this chain, so this is one root cause, not two.

<!-- fr:journal kind=finding scope=debug id=e824155a5eef created=2026-10-04T04:40:08+00:00 state=fixed -->
### e824155a5eef · finding [fixed] · Forge reads bounded; a failed read skips the pass in loop mode

`fr.gh._run_gh` passes `timeout=GH_TIMEOUT_SECONDS` (120s) and raises a transient `GhError` on `TimeoutExpired`. `triage_batch_cmd`: `recollect` (ForgeError), `_Driver.snapshot` and `_Driver.merge_ctx` (FORGE_ERRORS) raise `ForgeReadError`; the drive loop reports it once per cause (cleared on a good pass), sleeps `--interval` and retries; `--once`/plan mode keep exit 2 (re-collect) / 1 (in-pass read). Pinned failing-first by `tests/unit/test_gh.py#TestRunGhTimeout` (a real stalled `gh` stub) and `tests/unit/test_triage_batch_drive_cmd.py#test_a_failed_recollect_does_not_end_the_loop_and_is_reported_once`, `#test_a_failed_snapshot_read_does_not_end_the_loop`, `#test_a_failed_merge_method_read_does_not_end_the_loop`, `#test_once_still_exits_non_zero_on_a_failed_forge_read`. Fixed on the first attempt.

<!-- fr:journal kind=finding scope=debug id=fe16683779c4 created=2026-10-04T04:43:48+00:00 state=fixed -->
### fe16683779c4 · finding [fixed] · Review r1: act-time forge reads in a merge still crashed the loop

Independent review: `_Driver._merge_batch` caught only UnsupportedForgeOperation/MergeStopError/TriageError, so a `GhError` from `plan_queue`/`merge_ready`'s re-reads (`pr_view`, `pr_required_checks`, batch_merge.py:148/191/209/277/283) escaped as a traceback. Fixed: `except FORGE_ERRORS` → `ForgeReadError(code=1)` (the merge write itself is already a MergeStopError at batch_merge.py:307, so no write failure is swallowed). Pinned failing-first by `tests/unit/test_triage_batch_drive_cmd.py#test_a_failed_read_while_acting_on_a_merge_does_not_end_the_loop`.
