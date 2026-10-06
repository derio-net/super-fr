# Journal: 2026-10-06-batch-drive-restart-forge

<!-- fr:journal kind=hypothesis scope=debug id=h-one-root-cause created=2026-10-06T11:35:43+00:00 -->
### h-one-root-cause · hypothesis · Batch drive-restart-forge: investigation

Batch drive-restart-forge (#883, #921, #998) was placed as ONE root cause. Reading triage_batch_cmd.py/_Driver says it is not. (1) #883: _close_out appends CloseoutEvent only AFTER runner.dispatch; the restart dedupe in the gap is runner liveness (_existing / existing_dispatches), so a tab that ended before a restart is invisible. (2) #921 item 1: collect_facts drops a failing repo into facts.skipped in org scope; the drive never reads skipped, so its batches derive stages with no PRs (pr-open/merged read as dispatched). (3) #921 items 2-3, the push-rejection comment, and #998: the loop's only per-pass error boundary is ForgeReadError; git fetch failures (_archived/_released/merge_ctx), the archive merge refusal, a rejected update push and a strict TriageConfig refusal (recollect / _fresh_config) all route to _fail and end the process; gitseam._run has no timeout. (4) #921 item 4: GH_TIMEOUT_SECONDS uniform across paginated lists (low confidence). Verdict: three-to-four independent causes sharing a theme (the driver does not survive a disruption), not one. Stopped to ask the operator per the batch rule.

<!-- fr:journal kind=decision scope=debug id=d-operator-scope created=2026-10-06T13:36:42+00:00 -->
### d-operator-scope · decision · Batch drive-restart-forge: investigation

Operator (2026-10-06): fix all three causes in this one PR, each failing-test-first. #998: lenient read of .fr/triage.yaml inside the drive loop (unknown top-level keys warned once, ignored; hand-run collect/check stay strict) PLUS re-exec of the driver after post_merge installs a newer fr. #921.1: leave every batch of a skipped repo out of the pass, warned once per reason; Skipped unchanged.

<!-- fr:journal kind=repro scope=debug id=repro-failing-tests created=2026-10-06T13:42:00+00:00 -->
### repro-failing-tests · repro · Batch drive-restart-forge: investigation

tests/unit/test_triage_batch_drive_disruption.py: 18 fail + 3 error on main 2bee14589, each for the reported reason. #998: the merge path exits 2 with the live message '.fr/triage.yaml on the default branch is not valid triage config ... future_block Extra inputs are not permitted [type=extra_forbidden]' (check_config_fresh via merge_ctx/_fresh_config). #883: a driver killed after runner.dispatch, restarted once the tab ended, dispatches closeout-b1 twice (events at dispatch time: ['dispatch'] only). #921: a GitError from fetch (_released/_archived, merge_ctx) exits 2; a refused archive pr_merge exits 1; a rejected update push exits 2; gitseam._run passes no timeout; a skipped repo's proposed batch is dispatched.

<!-- fr:journal kind=root-cause scope=debug id=rc-883 created=2026-10-06T13:58:29+00:00 -->
### rc-883 · root-cause · Batch drive-restart-forge: investigation

gh#883: _Driver._close_out appended the CloseoutEvent only after runner.dispatch returned. In the gap, the only dedupe was runner liveness (_existing -> existing_dispatches), which cannot see a tab that already ended, so a driver killed after dispatch and restarted later started a second close-out.

<!-- fr:journal kind=root-cause scope=debug id=rc-921-boundary created=2026-10-06T13:58:44+00:00 -->
### rc-921-boundary · root-cause · Batch drive-restart-forge: investigation

gh#921 (2, 3, push comment) and the gh#998 exit: the drive loop has exactly one per-pass retry boundary, ForgeReadError. Git failures (_archived/_released/merge_ctx fetch), the archive pr_merge refusal, a rejected update push (GitError in _merge_batch) and a config refusal (recollect, _fresh_config) all routed to _fail and ended the process; gitseam._run started git with no timeout, so a stalled fetch blocked the loop.

<!-- fr:journal kind=root-cause scope=debug id=rc-921-skipped created=2026-10-06T13:58:46+00:00 -->
### rc-921-skipped · root-cause · Batch drive-restart-forge: investigation

gh#921 (1): collect_facts records a failing repo under facts.skipped in org/group scope, but the drive never read skipped; the repo stays in facts.repos, so its batches resolved with no PRs and derive_batch_stage misread pr-open/merged as dispatched (and a proposed one would dispatch on default config).

<!-- fr:journal kind=root-cause scope=debug id=rc-998 created=2026-10-06T13:58:48+00:00 -->
### rc-998 · root-cause · Batch drive-restart-forge: investigation

gh#998: TriageConfig is extra=forbid and the driver reads .fr/triage.yaml from the default branch every pass (collect read_config, check_config_fresh). The driver's own merges land a new key before the release that knows it, so the older running process refused the file and exited.

<!-- fr:journal kind=finding scope=debug id=f-883 created=2026-10-06T13:58:50+00:00 state=fixed -->
### f-883 · finding [fixed] · Batch drive-restart-forge: investigation

Close-out recorded before runner.dispatch (handle=item.id), rolled back on a dispatch failure, the runner's handle swapped in after. Pinned by test_the_closeout_is_recorded_before_its_tab_starts, test_a_restart_after_the_closeout_tab_ended_starts_no_second_closeout, test_a_closeout_the_runner_fails_to_start_is_not_left_recorded.
