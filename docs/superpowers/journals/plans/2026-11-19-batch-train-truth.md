<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-batch-train-truth

<!-- fr:journal kind=decision scope=plan id=p1-forge-read-keeps-its-branch created=2026-11-19T23:21:37+00:00 phase=1 -->
### p1-forge-read-keeps-its-branch · decision · A ForgeReadError keeps gh#910's fixed --interval retry inside the boundary (phase 1)

R3 lists every non-refusal as a transient with a doubling backoff and R5 stops after 10
failed passes. A ForgeReadError (a degraded forge, a clone fetch, the visibility read)
already had its own branch: reported once, retried every --interval, never ending the
loop (gh#910, gh#921, gh#1134), with tests pinning `naps == [7, 7]`. It now sits INSIDE
the one boundary and is counted in the ledger as cause `forge-read`, but keeps its fixed
interval and is not counted towards the 10-pass stop, so a long forge outage never stops
the driver as a refusal. Every other failure follows R3/R5 exactly. If the reviewer reads
R3/R5 as covering forge reads too, the change is two lines in `_loop`.

<!-- fr:journal kind=decision scope=plan id=p1-waits-are-not-pass-failures created=2026-11-19T23:21:37+00:00 phase=1 -->
### p1-waits-are-not-pass-failures · decision · An exception out of a wait passes the boundary untouched (`_WaitEnded`) (phase 1)

The boundary wraps the whole iteration, waits included (R1). A real sleep raises only
KeyboardInterrupt, but dozens of tests end the loop by raising from their `_sleep` hook.
Every loop wait goes through `_wait`, which carries such an exception as a BaseException
`_WaitEnded` past `except Exception`; `_host_loop` re-raises the original. Lease renewals
inside `wait_out` stay inside the boundary.

<!-- fr:journal kind=decision scope=plan id=p1-config-error-class created=2026-11-19T23:21:37+00:00 phase=1 -->
### p1-config-error-class · decision · New `fr.triage.errors.ConfigError`; `choose_method`'s config refusals raise it (phase 1)

R2 names "an invalid repo or triage config" a refusal, but no such class existed. A new
`ConfigError(TriageError)` is raised by `batch_merge.choose_method` (a merge method the
repo does not allow, none configured); `ForgeApiError` (an unusable `forge.api`) is a
refusal too. Both classify as `config:<Class>`. Being a TriageError subclass, every
existing handler still catches it.

<!-- fr:journal kind=decision scope=plan id=p1-triage-handlers-classify created=2026-11-19T23:21:37+00:00 phase=1 -->
### p1-triage-handlers-classify · decision · `_Driver`'s `except TriageError: _fail` sites raise `classify(exc)`, not the raw error (phase 1)

Letting the raw TriageError propagate would let an intermediate `except TriageError` in a
caller swallow what used to end the pass (a typer.Exit is no TriageError). Raising the
classified failure keeps exactly the old reach. `except UnsupportedForgeOperation: _fail`
and the ForgeApiError site were removed outright (neither is a TriageError, so no handler
between them and the boundary changes). Runner refusals and the single-pass guard raise
DriverRefusal (`runner-refused:<name>`, `runner-no-run-unit:<name>`, `single-pass`); a
runner's failed dispatch raises TransientPassFailure code 1 (`dispatch-failed:<name>`).

<!-- fr:journal kind=decision scope=plan id=p1-record-fields created=2026-11-19T23:21:37+00:00 phase=1 -->
### p1-record-fields · decision · The ledger keeps the exception class; driver.yaml keeps the last pass (phase 1)

R10's issue body names the exception class, so each ledger cause carries `exception`
beside the spec's fields. A scope with no state repo has no lease, so `driver.yaml` also
records `last_pass` on every clean looping pass; the stopped-driver need compares the
refusal with the later of the lease's and the record's last pass. The board shows the
stopped driver as its first note, and triage.html's Needs you now as `driver-stopped`.

<!-- fr:journal kind=decision scope=plan id=p1-failures-policy-and-adoption created=2026-11-19T23:21:37+00:00 phase=1 -->
### p1-failures-policy-and-adoption · decision · `drive failures --file` reads the target's policy remotely unless --checkout names its clone; adopts a marker-carrying open issue (phase 1)

A remote read sees only `.fr/settings.yaml`; `tracking: none` lives in a clone, so the
command takes `--checkout <clone>` to read the full policy. Comments obey
`forge.comments` and the label `forge.labels`. A cause with no recorded issue first
looks for an open issue carrying its marker (another host's filing) and adopts it, so
two hosts never file the same cause twice.

<!-- fr:journal kind=discovery scope=plan id=p1-tdd-order-t5 created=2026-11-19T23:21:37+00:00 phase=1 -->
### p1-tdd-order-t5 · discovery · T5's filing engine was written before its tests; the tests were green on their first run (phase 1)

Honest record of a TDD-order slip on P1.T5: `driver_failures.py` and the command were
written, then `test_failures_*`, which passed on their first run. Every other task went
red first (module missing, tripwire with 34 offences, the stub-driver loop tests).

<!-- fr:journal kind=discovery scope=plan id=p1-host-load-workers created=2026-11-19T23:21:37+00:00 phase=1 -->
### p1-host-load-workers · discovery · The host's load left the suite 2 xdist workers; the final suite ran with FR_PYTEST_WORKERS=6 (phase 1)

With other sessions' suites running (load ~20), `-n auto` started 2 workers and a full run
projected past 40 minutes. The final full suite ran as briefed but with
FR_PYTEST_WORKERS=6 (AGENTS.md's documented override); the test set is identical.

<!-- fr:journal kind=discovery scope=plan id=p1-executor-died-orchestrator-finished created=2026-11-19T23:21:37+00:00 phase=1 -->
### p1-executor-died-orchestrator-finished · discovery · The executor died before its final suite; the orchestrator merged main and finished the phase (phase 1)

The phase executor stopped after its three commits and this record, with its final suite
killed at 29%. The orchestrator merged origin/main (main had restructured the triage pages,
#1550: the stopped-driver input now threads through render_backlog → _sections →
_needs_section) and ran the full suite. It caught two phase-1 defects, fixed in 18870d9a2:
drive_errors.py imported click directly (no click on a clean install, so every scenario
test's candidate install failed at import; typer.Exit is the same class), and
driver_failures.file_failures' policy-gated forge writes were missing from the forge-write
tripwire's GATED list.
Verification: the post-merge full suite (16829 passed; the 2 failures and 83 errors
were these two defects). After the fix, a full rerun was killed externally at 42%
with no failure (host load ~32), so the failed set plus every scenario, tripwire,
triage, drive, render and backlog test reran: 4212 passed. CI runs the full suite on
the pushed head. `tests` evidence is left out: the logs were written by the
orchestrator, not by this unit's holder.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-19T23:21:37+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a smoke run and a change fragment: no code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-19T23:21:37+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

cleaned while going green: the per-site TriageError handlers became one `raise classify(exc) from exc`, the loop's deliberate ends became one LoopEnd return each, and batch_drive_command's typer.Exit handler collapsed into one lease rule on the returned code

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-19T23:21:37+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

driver_record.py was written once with one load/save pair per file; nothing duplicated to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-19T23:21:37+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

the filing engine sits in fr/triage/driver_failures.py and the command only resolves the target and policy; nothing to clean

<!-- fr:journal kind=review scope=plan id=review-phase-1-a created=2026-11-19T23:47:11+00:00 phase=1 -->
### review-phase-1-a · review · Independent review of phase 1 (R1-R10): 10 findings, all in scope (phase 1)

Reviewer (Opus, read-only) checked the branch diff against R1-R10 and the executor's
decisions. Classifier table, backoff arithmetic, the code-2 lease rule, host-locality,
the driver-stopped need and the merge's render threading were found correct; no
refusal can loop forever. Ten in-scope findings follow (p1a-r1..r10).

<!-- fr:journal kind=finding scope=plan id=p1a-r1 created=2026-11-19T23:47:11+00:00 phase=1 state=open review_scope=in -->
### p1a-r1 · finding [open] (reviewer: in scope) · classify() takes str(typer.Exit) = "2" as the message: an exit-based refusal records/shows "2" on driver.yaml, ledger and board, and --once prints "error: 2" again (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1a-r2 created=2026-11-19T23:47:11+00:00 phase=1 state=open review_scope=in -->
### p1a-r2 · finding [open] (reviewer: in scope) · non-rate-limit ForgeReadError keeps a fixed --interval and is not counted towards the 10-pass stop (nor resets it), contrary to R3/R5 as written (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1a-r3 created=2026-11-19T23:47:11+00:00 phase=1 state=open review_scope=in -->
### p1a-r3 · finding [open] (reviewer: in scope) · drive failures --file re-files a cause whose issue is CLOSED even when its count has not grown (no recurrence), contrary to R10 (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1a-r4 created=2026-11-19T23:47:11+00:00 phase=1 state=open review_scope=in -->
### p1a-r4 · finding [open] (reviewer: in scope) · closed-issue re-file ignores the open-marker adoption (cross-host duplicates), and a forge error mid-filing skips save_ledger, so reruns duplicate (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1a-r5 created=2026-11-19T23:47:11+00:00 phase=1 state=open review_scope=in -->
### p1a-r5 · finding [open] (reviewer: in scope) · cloud drive pass: non-rate-limit ForgeReadError still _fail()s without writing the outbox or counting the failure in the ledger (R6, R9) (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1a-r6 created=2026-11-19T23:47:11+00:00 phase=1 state=open review_scope=in -->
### p1a-r6 · finding [open] (reviewer: in scope) · R7 tripwire guards _host_loop but the loop body moved to _loop/_wait, which are unguarded (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1a-r7 created=2026-11-19T23:47:11+00:00 phase=1 state=open review_scope=in -->
### p1a-r7 · finding [open] (reviewer: in scope) · cloud drive pass refusal output does not name `fr triage drive failures --file --yes` (R10) (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1a-r8 created=2026-11-19T23:47:11+00:00 phase=1 state=open review_scope=in -->
### p1a-r8 · finding [open] (reviewer: in scope) · drive failures --file read-modify-writes the whole ledger, losing counts a running driver records meanwhile (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1a-r9 created=2026-11-19T23:47:11+00:00 phase=1 state=open review_scope=in -->
### p1a-r9 · finding [open] (reviewer: in scope) · drive failures --checkout is never verified to be a clone of the target repo whose policy gates filing (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1a-r10 created=2026-11-19T23:47:11+00:00 phase=1 state=open review_scope=in -->
### p1a-r10 · finding [open] (reviewer: in scope) · the 10th-transient stop rewrites the cause's ledger kind to refusal, mislabelling a transient cause and its filed issue (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1a-r1-resolved created=2026-11-19T23:47:11+00:00 phase=1 state=fixed resolves=p1a-r1 -->
### p1a-r1-resolved · finding [fixed] · resolves p1a-r1: classify() takes str(typer.Exit) = "2" as the message: an exit-based refusal records/shows "2" on driver.yaml, ledger and board, and --once prints "error: 2" again (phase 1)

_fail raises drive_errors.fail_exit, carrying fr_message; classify reads it, and every printer skips a message already said (09dc9ce94).

<!-- fr:journal kind=finding scope=plan id=p1a-r2-resolved created=2026-11-19T23:47:11+00:00 phase=1 state=fixed resolves=p1a-r2 -->
### p1a-r2-resolved · finding [fixed] · resolves p1a-r2: non-rate-limit ForgeReadError keeps a fixed --interval and is not counted towards the 10-pass stop (nor resets it), contrary to R3/R5 as written (phase 1)

Spec R3/R5 as written: the fixed-interval ForgeReadError branch is gone; a non-rate-limit forge read is a forge-read transient with doubling backoff, counted towards the stop (09dc9ce94).

<!-- fr:journal kind=finding scope=plan id=p1a-r3-resolved created=2026-11-19T23:47:11+00:00 phase=1 state=fixed resolves=p1a-r3 -->
### p1a-r3-resolved · finding [fixed] · resolves p1a-r3: drive failures --file re-files a cause whose issue is CLOSED even when its count has not grown (no recurrence), contrary to R10 (phase 1)

A closed cause is re-filed only when count > filed_count; otherwise '<issue> closed, no recurrence' (09dc9ce94).

<!-- fr:journal kind=finding scope=plan id=p1a-r4-resolved created=2026-11-19T23:47:11+00:00 phase=1 state=fixed resolves=p1a-r4 -->
### p1a-r4-resolved · finding [fixed] · resolves p1a-r4: closed-issue re-file ignores the open-marker adoption (cross-host duplicates), and a forge error mid-filing skips save_ledger, so reruns duplicate (phase 1)

A recurring closed cause adopts an open marker issue first; a forge error mid-filing becomes a line, what was filed is saved, exit 2 (09dc9ce94).

<!-- fr:journal kind=finding scope=plan id=p1a-r5-resolved created=2026-11-19T23:47:11+00:00 phase=1 state=fixed resolves=p1a-r5 -->
### p1a-r5-resolved · finding [fixed] · resolves p1a-r5: cloud drive pass: non-rate-limit ForgeReadError still _fail()s without writing the outbox or counting the failure in the ledger (R6, R9) (phase 1)

The cloud drive pass turns a forge read into a forge-read transient via _pass_failed: outbox written, ledger recorded, exit with its code (09dc9ce94).

<!-- fr:journal kind=finding scope=plan id=p1a-r6-resolved created=2026-11-19T23:47:11+00:00 phase=1 state=fixed resolves=p1a-r6 -->
### p1a-r6-resolved · finding [fixed] · resolves p1a-r6: R7 tripwire guards _host_loop but the loop body moved to _loop/_wait, which are unguarded (phase 1)

The R7 tripwire guards _loop, _wait and every boundary helper, and fails if a guarded name disappears (09dc9ce94).

<!-- fr:journal kind=finding scope=plan id=p1a-r7-resolved created=2026-11-19T23:47:11+00:00 phase=1 state=fixed resolves=p1a-r7 -->
### p1a-r7-resolved · finding [fixed] · resolves p1a-r7: cloud drive pass refusal output does not name `fr triage drive failures --file --yes` (R10) (phase 1)

The cloud refusal prints 'driver stopped (<cause>); resume: ...; track it: fr triage drive failures --file --yes' (09dc9ce94).

<!-- fr:journal kind=finding scope=plan id=p1a-r8-resolved created=2026-11-19T23:47:11+00:00 phase=1 state=fixed resolves=p1a-r8 -->
### p1a-r8-resolved · finding [fixed] · resolves p1a-r8: drive failures --file read-modify-writes the whole ledger, losing counts a running driver records meanwhile (phase 1)

Filing re-loads the ledger at save and merges only issue/filed_count of the causes it changed (driver_record.save_filed) (09dc9ce94).

<!-- fr:journal kind=finding scope=plan id=p1a-r9-resolved created=2026-11-19T23:47:11+00:00 phase=1 state=fixed resolves=p1a-r9 -->
### p1a-r9-resolved · finding [fixed] · resolves p1a-r9: drive failures --checkout is never verified to be a clone of the target repo whose policy gates filing (phase 1)

--checkout is refused unless its origin is the target repo; without one the command says tracking was not checked (09dc9ce94).

<!-- fr:journal kind=finding scope=plan id=p1a-r10-resolved created=2026-11-19T23:47:11+00:00 phase=1 state=fixed resolves=p1a-r10 -->
### p1a-r10-resolved · finding [fixed] · resolves p1a-r10: the 10th-transient stop rewrites the cause's ledger kind to refusal, mislabelling a transient cause and its filed issue (phase 1)

The 10th-transient stop keeps the ledger kind transient; only driver.yaml records the refusal (09dc9ce94).

<!-- fr:journal kind=discovery scope=plan id=p2-process-spawn-seam created=2026-11-20T02:48:00+00:00 phase=2 -->
### p2-process-spawn-seam · discovery · fr.triage may start no process outside its git seam: the child spawn lives in fr.safe_spawn.Child (phase 2)

The first full suite failed test_fr_triage_touches_gh_only_in_collect (supervise.py imported subprocess) and test_the_loop_ends_with_exit_3 (a new stop line printed to stdout). The spawn moved to fr.safe_spawn.Child (safe env, no new session); the final stop lines are log-only.

<!-- fr:journal kind=decision scope=plan id=p2-end-is-a-popen-returncode created=2026-11-20T02:48:00+00:00 phase=2 -->
### p2-end-is-a-popen-returncode · decision · restart_decision takes a Popen return code; the driver's clean stop is exit 130 (phase 2)

A signal death is a negative return code. SIGINT/SIGTERM/SIGHUP deaths (-n) and exit 128+n are deliberate stops (code 128+n). Typer turns the driver's KeyboardInterrupt (Ctrl-C and SIGTERM) into exit 1, which would read as a crash, so a driver started with --supervised-by exits 130 on KeyboardInterrupt (after releasing its lease). A stop the supervisor itself causes (its own signal, or its parent ending) never restarts and exits 0.

<!-- fr:journal kind=decision scope=plan id=p2-status-without-lease created=2026-11-20T02:48:00+00:00 phase=2 -->
### p2-status-without-lease · decision · drive status with no lease still reports a live recorded driver on this host (phase 2)

A scope with no state repo holds no lease at all (_host_lease returns None), so a lease-only status could never exit 0 there. driver.yaml is host-local, so with no lease a record whose pid is alive reads as running (exit 0); no lease and no record, or a dead pid, is exit 3. A live lease of another host is reported as held elsewhere (exit 0, never probed); an expired one is exit 3.

<!-- fr:journal kind=decision scope=plan id=p2-supervised-wait-is-chunked created=2026-11-20T02:48:00+00:00 phase=2 -->
### p2-supervised-wait-is-chunked · decision · A supervised driver's every wait is cut into one-second sleeps through _wait (phase 2)

R12 asks for a ppid check inside the module-level _sleep and wait_out. Both reach the clock through _wait, so _wait splits a supervised wait into one-second _sleep calls and checks os.getppid() between them (SupervisorGone, a BaseException, passes the pass boundary; _host_loop returns LoopEnd(0) and the command releases the lease). Unsupervised, _wait is one _sleep as before.

<!-- fr:journal kind=decision scope=plan id=p2-log-routing created=2026-11-20T02:48:00+00:00 phase=2 -->
### p2-log-routing · decision · _say routes through _emit; the drive log is attached only in loop mode with --yes (phase 2)

_emit(kind, line) prints and appends while drive_log_attached is active; _say is _emit('action', ...). The log is attached around the host loop only when --yes and not --once, so plan mode and --once are byte-identical. Pass summaries are kind pass, a stall or the final stop is stop, warnings are transient, refusals refusal; the supervisor writes restart and stop. A log write that fails is swallowed: the log is a view.

<!-- fr:journal kind=discovery scope=plan id=p2-tdd-order-supervisor created=2026-11-20T02:48:00+00:00 phase=2 -->
### p2-tdd-order-supervisor · discovery · The supervisor and drive log were written before their tests; the tests were green on first run (phase 2)

Honest record of a TDD-order slip on P2.T2/P2.T4: supervise.py and drive_log.py were drafted with the pure policy tests only (T1 went red first: module missing); the process, log and command tests followed the code and passed, except the parent-death test, which exposed a real race (a parent that exits before the supervisor reads its ppid is never seen to change); the test now holds its parent until the driver started.

<!-- fr:journal kind=discovery scope=plan id=p2-docs-pages-deferred created=2026-11-20T02:48:00+00:00 phase=2 -->
### p2-docs-pages-deferred · discovery · fr docs check lists fr-triage, fr-wave-driver and herdr-control-sessions as stale until phase 4 (phase 2)

The plan puts the explainer and skill pages last (phase 4), so the stale-page report on this branch is expected after phase 2.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-20T02:48:00+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

restart_decision is a pure function written once; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-20T02:48:00+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

Supervisor was written in one pass; the supervised-driver checks reuse the loop's one _wait seam, nothing duplicated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-20T02:48:00+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

status and log are small read-only commands sharing _status_tail; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-20T02:48:00+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

_say became a thin wrapper of _emit, the one print-and-append seam; nothing left to fold

<!-- fr:journal kind=review scope=plan id=review-phase-2-a created=2026-11-20T03:01:25+00:00 phase=2 -->
### review-phase-2-a · review · Phase 2 review: supervisor, drive_log, drive status/log, Activity panel (phase 2)

Independent read-only review of `git diff 2829d71e7 7fc3bc303` against spec R11-R14, R22-R23. Seven findings, all in scope; checked fine: exit 2/3 not restarted, 129/130/143 and signal codes deliberate, supervisor never detaches, SupervisorGone not swallowed by the pass boundary, no click import, subprocess only in safe_spawn, no new forge write.

<!-- fr:journal kind=finding scope=plan id=p2a-r1 created=2026-11-20T03:01:25+00:00 phase=2 state=open review_scope=in -->
### p2a-r1 · finding [open] (reviewer: in scope) · crash-loop stop is only ledgered and logged: no driver.yaml last_refusal, no board render, nothing printed, no failures-command pointer (R11/R8/R22) (phase 2)

crash-loop stop is only ledgered and logged: no driver.yaml last_refusal, no board render, nothing printed, no failures-command pointer (R11/R8/R22)

<!-- fr:journal kind=finding scope=plan id=p2a-r2 created=2026-11-20T03:01:25+00:00 phase=2 state=open review_scope=in -->
### p2a-r2 · finding [open] (reviewer: in scope) · drive status exits 0 on pid liveness alone when no lease exists; a reused pid reports a dead driver as running (R14) (phase 2)

drive status exits 0 on pid liveness alone when no lease exists; a reused pid reports a dead driver as running (R14)

<!-- fr:journal kind=finding scope=plan id=p2a-r3 created=2026-11-20T03:01:25+00:00 phase=2 state=open review_scope=in -->
### p2a-r3 · finding [open] (reviewer: in scope) · drive status says no driver holds the scope (exit 3) during restart backoff while the supervisor is alive (R14) (phase 2)

drive status says no driver holds the scope (exit 3) during restart backoff while the supervisor is alive (R14)

<!-- fr:journal kind=finding scope=plan id=p2a-r4 created=2026-11-20T03:01:25+00:00 phase=2 state=open review_scope=in -->
### p2a-r4 · finding [open] (reviewer: in scope) · DriveLog.append rotation is unlocked: driver and supervisor racing at the limit can replace drive.log.1 with a near-empty file (R22) (phase 2)

DriveLog.append rotation is unlocked: driver and supervisor racing at the limit can replace drive.log.1 with a near-empty file (R22)

<!-- fr:journal kind=finding scope=plan id=p2a-r5 created=2026-11-20T03:01:25+00:00 phase=2 state=open review_scope=in -->
### p2a-r5 · finding [open] (reviewer: in scope) · drive log -f loses lines appended between tail() and follow()'s end-seek; BrokenPipe not handled (R22) (phase 2)

drive log -f loses lines appended between tail() and follow()'s end-seek; BrokenPipe not handled (R22)

<!-- fr:journal kind=finding scope=plan id=p2a-r6 created=2026-11-20T03:01:25+00:00 phase=2 state=open review_scope=in -->
### p2a-r6 · finding [open] (reviewer: in scope) · the sixth crash is never ledgered as crash:<x> because the crash-loop branch returns first (R13) (phase 2)

the sixth crash is never ledgered as crash:<x> because the crash-loop branch returns first (R13)

<!-- fr:journal kind=finding scope=plan id=p2a-r7 created=2026-11-20T03:01:25+00:00 phase=2 state=open review_scope=in -->
### p2a-r7 · finding [open] (reviewer: in scope) · tests lack real-driver 130/SIGHUP cases, concurrent append and rotation races, crash-loop last_refusal, and status with no lease plus a live unrelated pid (phase 2)

tests lack real-driver 130/SIGHUP cases, concurrent append and rotation races, crash-loop last_refusal, and status with no lease plus a live unrelated pid

<!-- fr:journal kind=finding scope=plan id=p2a-r1-resolved created=2026-11-20T03:01:25+00:00 phase=2 state=fixed resolves=p2a-r1 -->
### p2a-r1-resolved · finding [fixed] · resolves p2a-r1: crash-loop stop is only ledgered and logged: no driver.yaml last_refusal, no board render, nothing printed, no failures-command pointer (R11/R8/R22) (phase 2)

Supervisor records last_refusal via record_refusal(..., as_supervisor=True), renders the board once from disk (on_refusal callback, no forge reads), and prints every line (incl. the resume command and the `fr triage drive failures --file --yes` pointer) to stderr as well as drive.log; the crash-loop integration test asserts all three. Commits ed163871d, 626857363; targeted run 3910 passed (p2-fix.log).

<!-- fr:journal kind=finding scope=plan id=p2a-r2-resolved created=2026-11-20T03:01:25+00:00 phase=2 state=fixed resolves=p2a-r2 -->
### p2a-r2-resolved · finding [fixed] · resolves p2a-r2: drive status exits 0 on pid liveness alone when no lease exists; a reused pid reports a dead driver as running (R14) (phase 2)

driver.yaml records pid_start/supervised_start (fr.safe_spawn.process_start); drive status requires the live start time to match, and trusts a record without one only under a live lease of this host. Tests: unrelated live pid with no lease exits 3, matching start exits 0. Commits ed163871d, 626857363; targeted run 3910 passed (p2-fix.log).

<!-- fr:journal kind=finding scope=plan id=p2a-r3-resolved created=2026-11-20T03:01:25+00:00 phase=2 state=fixed resolves=p2a-r3 -->
### p2a-r3-resolved · finding [fixed] · resolves p2a-r3: drive status says no driver holds the scope (exit 3) during restart backoff while the supervisor is alive (R14) (phase 2)

A dead child with a live, start-matched supervisor reports 'supervisor alive, driver restarting', exit 0; match and mismatch tested. Commits ed163871d, 626857363; targeted run 3910 passed (p2-fix.log).

<!-- fr:journal kind=finding scope=plan id=p2a-r4-resolved created=2026-11-20T03:01:25+00:00 phase=2 state=fixed resolves=p2a-r4 -->
### p2a-r4-resolved · finding [fixed] · resolves p2a-r4: DriveLog.append rotation is unlocked: driver and supervisor racing at the limit can replace drive.log.1 with a near-empty file (R22) (phase 2)

Size check, rotation and write run under fcntl.flock on drive.log.lock with a re-stat under the lock; tail takes a shared lock; concurrent-appender test asserts drive.log.1 is never a near-empty replacement and no line is torn. Commits ed163871d, 626857363; targeted run 3910 passed (p2-fix.log).

<!-- fr:journal kind=finding scope=plan id=p2a-r5-resolved created=2026-11-20T03:01:25+00:00 phase=2 state=fixed resolves=p2a-r5 -->
### p2a-r5-resolved · finding [fixed] · resolves p2a-r5: drive log -f loses lines appended between tail() and follow()'s end-seek; BrokenPipe not handled (R22) (phase 2)

DriveLog.follow(tail=N) takes tail and follow offset from one read, drains the old file across a rotation, and ends quietly on BrokenPipeError; tests cover each. Commits ed163871d, 626857363; targeted run 3910 passed (p2-fix.log).

<!-- fr:journal kind=finding scope=plan id=p2a-r6-resolved created=2026-11-20T03:01:25+00:00 phase=2 state=fixed resolves=p2a-r6 -->
### p2a-r6-resolved · finding [fixed] · resolves p2a-r6: the sixth crash is never ledgered as crash:<x> because the crash-loop branch returns first (R13) (phase 2)

The final crash is ledgered as crash:<x> before the crash-loop refusal; pinned count is now 6. Commits ed163871d, 626857363; targeted run 3910 passed (p2-fix.log).

<!-- fr:journal kind=finding scope=plan id=p2a-r7-resolved created=2026-11-20T03:01:25+00:00 phase=2 state=fixed resolves=p2a-r7 -->
### p2a-r7-resolved · finding [fixed] · resolves p2a-r7: tests lack real-driver 130/SIGHUP cases, concurrent append and rotation races, crash-loop last_refusal, and status with no lease plus a live unrelated pid (phase 2)

Added tests: real `batch drive --supervised-by` exiting 130 read as Stop(130) with the lease released, SupervisorGone releasing the lease, SIGHUP stop without restart, real process-start read, plus the r1-r5 tests. Commits ed163871d, 626857363; targeted run 3910 passed (p2-fix.log).

<!-- fr:journal kind=decision scope=plan id=p3-probe-scope-and-memo created=2026-11-20T08:48:33+00:00 phase=3 -->
### p3-probe-scope-and-memo · decision · conflict-probe covers every conflicting non-candidate; the memo holds the paths, per driver process (phase 3)

The walks emit `conflict-probe` for each OPEN batch PR that reads conflicting except the
merge train's candidates (merge-train mode) and PRs already in the merge queue (queue mode).
A conflicting non-member (unapproved draft) is also stepped over and puts a Train in the
pass, so the train line names it (R16). `_Driver._probed` maps (repo, PR, head, default
branch sha) to the refused paths, so a session that was working or unreadable is retried
on the next pass from the cached paths with no second trial merge. A `conflict` event at
the head is the `skip` and is decided with no I/O. The probe's scratch root is
`<state dir>/probe/`, and trial_conflicts removes the worktree in a `finally`.

<!-- fr:journal kind=decision scope=plan id=p3-probe-no-session-held created=2026-11-20T08:48:33+00:00 phase=3 -->
### p3-probe-no-session-held · decision · a runner that cannot be inspected or messaged counts as no session for the probe: held (phase 3)

`_offer` returns None for a runner that is neither inspector nor messenger. The conflict
hand-back would start a fresh session; the probe never does (R17), so None, absent and
done are all `conflict` event `delivered: held`; idle messages; working, unknown and a
failed read wait.

<!-- fr:journal kind=decision scope=plan id=p3-card-hint-placement created=2026-11-20T08:48:33+00:00 phase=3 -->
### p3-card-hint-placement · decision · the card hint `conflicting - handed back` sits after the lane/stop/idle hints and yields to a red phrase (phase 3)

R18's hint (`CONFLICT_HANDED_BACK_HINT`, mergeability.py) is chosen only for a delivered
`conflict` event at the PR's current head, after every needs-you hint and before the
driver-action and awaiting-approval ones; a red PR keeps its red phrase.

<!-- fr:journal kind=discovery scope=plan id=p3-t1s3-green-first created=2026-11-20T08:48:33+00:00 phase=3 -->
### p3-t1s3-green-first · discovery · P3.T1.S3 (red recovery for an unapproved draft) was green on its first run (phase 3)

As the plan expected, _recover needs nothing beyond the walk's new `warn red=True`: the
five command tests for idle / working / absent / done / the cross-draft-and-ready cap
passed at once. P3.T1.S1 went red (4 of 6 failed) and P3.T2/T3/T4 each went red first.

<!-- fr:journal kind=discovery scope=plan id=p3-drive-is-one-process created=2026-11-20T08:48:33+00:00 phase=3 -->
### p3-drive-is-one-process · discovery · the per-process memo needs a looping drive in a test; each `--once` is a new process (phase 3)

`_drive(..., "--once")` builds a new _Driver per call, so the once-per-process trial
merge is shown through a loop run with a `_sleep` hook. The existing pass also reads each
batch PR twice (the snapshot and `settle_approvals`); the probe adds no read, which the
test checks against the clean-PR count.

<!-- fr:journal kind=discovery scope=plan id=p3-scenario-caught-launch-requirement created=2026-11-20T08:48:33+00:00 phase=3 -->
### p3-scenario-caught-launch-requirement · discovery · the cloud-triage-version-drift scenario failed on the first full suite: a red draft's hand-back asked for a launch model (phase 3)

The scenario's batches are unapproved drafts with no `launch.model`. Now that they are
walked as red non-members, `_recover` reached `_hand_back_target`, whose `_launch` raises
for a batch with no model, ending the pass with code 2. A message to a session never
starts one, so `_session_target` (name and work item, no launch) now serves `_recover`
and `_probe_conflict`; `_hand_back_target` builds on it. Test:
test_a_hand_back_to_a_session_needs_no_model_to_launch_with (red before, green after).
The same run's other failure, test_run_evidence_visual
test_an_ignored_shot_inside_the_repo_passes_through_git, passed alone and is load-flaky
(host load ~45); the log of that first run is p3-suite-run1.log beside the final one.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-20T08:48:33+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

the member split is one helper (_nonmember) shared by both walks; nothing duplicated to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-20T08:48:33+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

_update's merge step and _unresolvable were factored into merge_main/trial_conflicts as the green step itself; nothing further to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t4 created=2026-11-20T08:48:33+00:00 phase=3 -->
### no-refactor-p3-t4 · discovery · no-refactor-because P3.T4 (phase 3)

a four-line change beside _fetched; nothing to clean

<!-- fr:journal kind=review scope=plan id=review-phase-3-a created=2026-11-20T10:15:25+00:00 phase=3 -->
### review-phase-3-a · review · Phase 3 review: red and conflicting draft hand-backs, train-wide probe, one fetch per pass (phase 3)

Independent read-only review of b2725d115, 4c802828a and 1d03aafa7 against spec R15-R19. R15-R18 built as written; held-on-uninspectable-runner decision matches the spec. Six findings, all in scope.

<!-- fr:journal kind=finding scope=plan id=p3a-r1 created=2026-11-20T10:15:25+00:00 phase=3 state=open review_scope=in -->
### p3a-r1 · finding [open] (reviewer: in scope) · merge_ctx fetched directly, ignoring _fetched/_fetch_failed, so a failed fetch repeated within one pass (R19) (phase 3)

merge_ctx fetched directly, ignoring _fetched/_fetch_failed, so a failed fetch repeated within one pass (R19)

<!-- fr:journal kind=finding scope=plan id=p3a-r2 created=2026-11-20T10:15:25+00:00 phase=3 state=open review_scope=in -->
### p3a-r2 · finding [open] (reviewer: in scope) · _recover fetched per red PR, bypassing the one-fetch-per-repo-per-pass cache and its failure record (R19) (phase 3)

_recover fetched per red PR, bypassing the one-fetch-per-repo-per-pass cache and its failure record (R19)

<!-- fr:journal kind=finding scope=plan id=p3a-r3 created=2026-11-20T10:15:25+00:00 phase=3 state=open review_scope=in -->
### p3a-r3 · finding [open] (reviewer: in scope) · _session_target resolved a launch (needs a model) when the batch had no dispatch event, failing the pass (phase 3)

_session_target resolved a launch (needs a model) when the batch had no dispatch event, failing the pass

<!-- fr:journal kind=finding scope=plan id=p3a-r4 created=2026-11-20T10:15:25+00:00 phase=3 state=open review_scope=in -->
### p3a-r4 · finding [open] (reviewer: in scope) · _probe_conflict's wait-behind, nothing-sent and hand-back-failed lines printed every pass (phase 3)

_probe_conflict's wait-behind, nothing-sent and hand-back-failed lines printed every pass

<!-- fr:journal kind=finding scope=plan id=p3a-r5 created=2026-11-20T10:15:25+00:00 phase=3 state=open review_scope=in -->
### p3a-r5 · finding [open] (reviewer: in scope) · trial_conflicts' cleanup could mask the in-flight exception and skip temp-root cleanup; a leftover dirty probe dir blocked probing forever (phase 3)

trial_conflicts' cleanup could mask the in-flight exception and skip temp-root cleanup; a leftover dirty probe dir blocked probing forever

<!-- fr:journal kind=finding scope=plan id=p3a-r6 created=2026-11-20T10:15:25+00:00 phase=3 state=open review_scope=in -->
### p3a-r6 · finding [open] (reviewer: in scope) · tests missed queue-mode red hand-back, uninspectable runner -> held, probe fetch failure, carries=False (phase 3)

tests missed queue-mode red hand-back, uninspectable runner -> held, probe fetch failure, carries=False

<!-- fr:journal kind=finding scope=plan id=p3-orch-r12-parent-race created=2026-11-20T10:15:25+00:00 phase=3 state=open review_scope=in -->
### p3-orch-r12-parent-race · finding [open] (reviewer: in scope) · The supervisor read getppid() late: a launcher that ended first left it adopted and running forever (R12) (phase 3)

Found by the orchestrator: a parent-death test's supervisor and driver ran orphaned for ~6 h on a loaded host; the existing test also raced reading the child's ppid (2 of 15 local runs failed).

<!-- fr:journal kind=finding scope=plan id=p3a-r1-resolved created=2026-11-20T10:15:25+00:00 phase=3 state=fixed resolves=p3a-r1 -->
### p3a-r1-resolved · finding [fixed] · resolves p3a-r1: merge_ctx fetched directly, ignoring _fetched/_fetch_failed, so a failed fetch repeated within one pass (R19) (phase 3)

New _fetch_once records success and failure; merge_ctx and _fetched_reader both go through it, so a recorded failure re-raises the same GitError without fetching. Tests cover both orders. Commit 26a9a9231; scoped run 7785 passed (p3-fix.log).

<!-- fr:journal kind=finding scope=plan id=p3a-r2-resolved created=2026-11-20T10:15:25+00:00 phase=3 state=fixed resolves=p3a-r2 -->
### p3a-r2-resolved · finding [fixed] · resolves p3a-r2: _recover fetched per red PR, bypassing the one-fetch-per-repo-per-pass cache and its failure record (R19) (phase 3)

_recover reads through self._fetched_reader(repo).rev_parse(ctx.main); test: a red pass fetches the repo once. _base_now's fetch predates this branch (unchanged against origin/main) and is left as is. Commit 26a9a9231; scoped run 7785 passed (p3-fix.log).

<!-- fr:journal kind=finding scope=plan id=p3a-r3-resolved created=2026-11-20T10:15:25+00:00 phase=3 state=fixed resolves=p3a-r3 -->
### p3a-r3-resolved · finding [fixed] · resolves p3a-r3: _session_target resolved a launch (needs a model) when the batch had no dispatch event, failing the pass (phase 3)

_session_target takes the runner from the dispatch event, else adapter.runner_for(batch), else batch.launch.runner, and never resolves a launch; no runner reads as absent (red) or held (probe). Unit-tested directly. Commit 26a9a9231; scoped run 7785 passed (p3-fix.log).

<!-- fr:journal kind=finding scope=plan id=p3a-r4-resolved created=2026-11-20T10:15:25+00:00 phase=3 state=fixed resolves=p3a-r4 -->
### p3a-r4-resolved · finding [fixed] · resolves p3a-r4: _probe_conflict's wait-behind, nothing-sent and hand-back-failed lines printed every pass (phase 3)

New _probe_said dedupes by batch, head and cause; two-pass loop tests show each line once. Commit 26a9a9231; scoped run 7785 passed (p3-fix.log).

<!-- fr:journal kind=finding scope=plan id=p3a-r5-resolved created=2026-11-20T10:15:25+00:00 phase=3 state=fixed resolves=p3a-r5 -->
### p3a-r5-resolved · finding [fixed] · resolves p3a-r5: trial_conflicts' cleanup could mask the in-flight exception and skip temp-root cleanup; a leftover dirty probe dir blocked probing forever (phase 3)

Cleanup GitError suppressed, temp root always removed, a leftover probe-<head12> force-removed (rmtree fallback) before the probe; tests for KeyboardInterrupt mid-merge, merge GitError, failing cleanup, leftover dir, and a said-once uncached retry. Commit 26a9a9231; scoped run 7785 passed (p3-fix.log).

<!-- fr:journal kind=finding scope=plan id=p3a-r6-resolved created=2026-11-20T10:15:25+00:00 phase=3 state=fixed resolves=p3a-r6 -->
### p3a-r6-resolved · finding [fixed] · resolves p3a-r6: tests missed queue-mode red hand-back, uninspectable runner -> held, probe fetch failure, carries=False (phase 3)

Added each as a test. Commit 26a9a9231; scoped run 7785 passed (p3-fix.log).

<!-- fr:journal kind=finding scope=plan id=p3-orch-r12-parent-race-resolved created=2026-11-20T10:15:25+00:00 phase=3 state=fixed resolves=p3-orch-r12-parent-race -->
### p3-orch-r12-parent-race-resolved · finding [fixed] · resolves p3-orch-r12-parent-race: The supervisor read getppid() late: a launcher that ended first left it adopted and running forever (R12) (phase 3)

Supervisor takes the parent explicitly and stops before starting a driver when it already ended; the rig names its parent and the supervisor names itself; a new test (parent ended before run) and the repaired race both failed before the fix and pass after. Commit c28d94e42.

<!-- fr:journal kind=discovery scope=plan id=p4-r20-test-green-first created=2026-11-20T10:42:43+00:00 phase=4 -->
### p4-r20-test-green-first · discovery · R20's partial-apply test was green first (phase 4) (phase 4)

swap_issue_labels already repeated idempotent adds and removals, so the test proving a refused call that applied its add ends with the wanted labels passed before the docstring changed; the change is the docstring (P4.T1.S2). The R21 test was red first.

<!-- fr:journal kind=decision scope=plan id=p4-docs-landed-early created=2026-11-20T10:42:43+00:00 phase=4 -->
### p4-docs-landed-early · decision · R24 docs landed ahead of the phase (phase 4) (phase 4)

The R24 docs and mirrors landed in f050390cd and 4b8171acb ahead of this phase so CI's docs-check could pass. Re-verified against phase 3's review fixes (26a9a9231, c28d94e42): added the no-session conflict hold and the R21 cancel wording, re-synced the three mirrors, fr docs check --base origin/main exits 0.

<!-- fr:journal kind=decision scope=plan id=p4-cancel-gate-on-dispatch created=2026-11-20T10:42:43+00:00 phase=4 -->
### p4-cancel-gate-on-dispatch · decision · cancel gates and withdraws on a dispatch event, not on stage (phase 4) (phase 4)

batch cancel now computes dispatched from the events; without one, withdraws is empty and no tracking gate or clone is needed. Claims are still released (their label removal is the claim release, not a withdrawal).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-11-20T10:42:43+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

a docstring reword and one test; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-11-20T10:42:43+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

one computed flag replaced the stage test; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t3 created=2026-11-20T10:42:43+00:00 phase=4 -->
### no-refactor-p4-t3 · discovery · no-refactor-because P4.T3 (phase 4)

docs and generated mirrors only

<!-- fr:journal kind=review scope=plan id=review-phase-4-a created=2026-11-20T10:53:42+00:00 phase=4 -->
### review-phase-4-a · review · Phase 4 review: swap-labels idempotence, clone-free cancel, R24 docs (phase 4)

Independent read-only review of 1de111c8a, f050390cd and 4b8171acb against R20, R21, R24. R20 and R21 built as written; every docs number checked against code. Four minor findings, all in scope.

<!-- fr:journal kind=finding scope=plan id=p4a-r1 created=2026-11-20T10:53:42+00:00 phase=4 state=open review_scope=in -->
### p4a-r1 · finding [open] (reviewer: in scope) · SKILL.md said a failed forge read is retried after --interval; the code uses the doubling transient backoff (phase 4)

SKILL.md said a failed forge read is retried after --interval; the code uses the doubling transient backoff

<!-- fr:journal kind=finding scope=plan id=p4a-r2 created=2026-11-20T10:53:42+00:00 phase=4 state=open review_scope=in -->
### p4a-r2 · finding [open] (reviewer: in scope) · fr-wave-driver.md said a signal stop ends the supervisor with the same code; supervise.py returns 128+signal (phase 4)

fr-wave-driver.md said a signal stop ends the supervisor with the same code; supervise.py returns 128+signal

<!-- fr:journal kind=finding scope=plan id=p4a-r3 created=2026-11-20T10:53:42+00:00 phase=4 state=open review_scope=in -->
### p4a-r3 · finding [open] (reviewer: in scope) · a never-dispatched cancel still printed 'held by another scope; label and comments left to it' (phase 4)

a never-dispatched cancel still printed 'held by another scope; label and comments left to it'

<!-- fr:journal kind=finding scope=plan id=p4a-r4 created=2026-11-20T10:53:42+00:00 phase=4 state=open review_scope=in -->
### p4a-r4 · finding [open] (reviewer: in scope) · the R21 test seeded no fr:in-progress label, so 'removes no label' was weakly proven (phase 4)

the R21 test seeded no fr:in-progress label, so 'removes no label' was weakly proven

<!-- fr:journal kind=finding scope=plan id=p4a-r1-resolved created=2026-11-20T10:53:42+00:00 phase=4 state=fixed resolves=p4a-r1 -->
### p4a-r1-resolved · finding [fixed] · resolves p4a-r1: SKILL.md said a failed forge read is retried after --interval; the code uses the doubling transient backoff (phase 4)

The skill now says the read is retried after the transient backoff (--interval, doubling to 15 minutes); mirrors regenerated. Commit f2f927670.

<!-- fr:journal kind=finding scope=plan id=p4a-r2-resolved created=2026-11-20T10:53:42+00:00 phase=4 state=fixed resolves=p4a-r2 -->
### p4a-r2-resolved · finding [fixed] · resolves p4a-r2: fr-wave-driver.md said a signal stop ends the supervisor with the same code; supervise.py returns 128+signal (phase 4)

The explainer now says a signal stop ends with 128 plus the signal number. Commit f2f927670.

<!-- fr:journal kind=finding scope=plan id=p4a-r3-resolved created=2026-11-20T10:53:42+00:00 phase=4 state=fixed resolves=p4a-r3 -->
### p4a-r3-resolved · finding [fixed] · resolves p4a-r3: a never-dispatched cancel still printed 'held by another scope; label and comments left to it' (phase 4)

That line prints only for a dispatched batch. Commit f2f927670.

<!-- fr:journal kind=finding scope=plan id=p4a-r4-resolved created=2026-11-20T10:53:42+00:00 phase=4 state=fixed resolves=p4a-r4 -->
### p4a-r4-resolved · finding [fixed] · resolves p4a-r4: the R21 test seeded no fr:in-progress label, so 'removes no label' was weakly proven (phase 4)

The test now seeds fr:in-progress and asserts it stays. That exposed a real gap: the claim release removed fr:in-progress (claim_sync always unlabels). ClaimOp gains unlabel (default True); cancel passes unlabel=dispatched, so a never-dispatched cancel removes only fr:claimed. Claim/cancel tests: 347 passed. Commit f2f927670.

<!-- fr:journal kind=review scope=plan id=lens-review-a created=2026-11-20T13:25:14+00:00 -->
### lens-review-a · review · Lens review: errors, tests, simplicity, docs-accuracy over the whole feature

One read-only reviewer per lens over merge-base 396e444d3..HEAD. 22 in-scope findings (21 fixed, 1 refuted with the spec's reason) and 1 out of scope, filed as derio-net/super-fr#1601.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · --once/plan mode: an unexpected exception exited 2 (was traceback, exit 1) and printed nothing on an empty message

--once/plan mode: an unexpected exception exited 2 (was traceback, exit 1) and printed nothing on an empty message

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · looping and cloud drivers kept no traceback for unexpected:* causes

looping and cloud drivers kept no traceback for unexpected:* causes

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-errors-r3 · finding [open] (reviewer: in scope) · a bare typer.Exit(2) from _load_state/resolve_state_dir inside a pass became a refusal with an empty message

a bare typer.Exit(2) from _load_state/resolve_state_dir inside a pass became a refusal with an empty message

<!-- fr:journal kind=finding scope=plan id=l-errors-r4 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-errors-r4 · finding [open] (reviewer: in scope) · refusals raised through _fail never wrote their reason to drive.log

refusals raised through _fail never wrote their reason to drive.log

<!-- fr:journal kind=finding scope=plan id=l-errors-r5 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-errors-r5 · finding [open] (reviewer: in scope) · the supervisor's Child() OSError killed it with a traceback and recorded nothing; its record/ledger writes failed silently

the supervisor's Child() OSError killed it with a traceback and recorded nothing; its record/ledger writes failed silently

<!-- fr:journal kind=finding scope=plan id=l-errors-r6 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-errors-r6 · finding [open] (reviewer: in scope) · trial_conflicts cleanup swallowed failures and its rmtree fallback skipped prune, so a stale registration blocked the probe

trial_conflicts cleanup swallowed failures and its rmtree fallback skipped prune, so a stale registration blocked the probe

<!-- fr:journal kind=finding scope=plan id=l-errors-r7 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-errors-r7 · finding [open] (reviewer: in scope) · an invalid scope config read in take_lease was transient triage:TriageError instead of an R2 refusal

an invalid scope config read in take_lease was transient triage:TriageError instead of an R2 refusal

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · supervisor process test cleanup could leak a launcher-started supervisor and an unwritten-pid driver forever

supervisor process test cleanup could leak a launcher-started supervisor and an unwritten-pid driver forever

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · a fixed sleep raced the fake driver's SIG_IGN

a fixed sleep raced the fake driver's SIG_IGN

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · the R20 swap_issue_labels test passed without the retry

the R20 swap_issue_labels test passed without the retry

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · no test moved the PR head or default-branch sha between passes, so a PR-only probe cache would pass

no test moved the PR head or default-branch sha between passes, so a PR-only probe cache would pass

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-tests-r5 · finding [open] (reviewer: in scope) · no test exercised the old-file drain at a DriveLog rotation

no test exercised the old-file drain at a DriveLog rotation

<!-- fr:journal kind=finding scope=plan id=l-tests-r6 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-tests-r6 · finding [open] (reviewer: in scope) · R17's lockfile case had no trial_conflicts test

R17's lockfile case had no trial_conflicts test

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r1 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-simplicity-r1 · finding [open] (reviewer: in scope) · three near-identical dedupe-once helpers with inconsistent keys

three near-identical dedupe-once helpers with inconsistent keys

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r2 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-simplicity-r2 · finding [open] (reviewer: in scope) · drive_errors derives a cause from traceback frame names; have _fail raise with an explicit cause

drive_errors derives a cause from traceback frame names; have _fail raise with an explicit cause

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r3 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-simplicity-r3 · finding [open] (reviewer: in scope) · _fail duplicated in triage_drive_cmd and triage_kanban_cmd

_fail duplicated in triage_drive_cmd and triage_kanban_cmd

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r4 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-simplicity-r4 · finding [open] (reviewer: in scope) · driver_record repeated the load-or-None block and loaded twice in record_refusal

driver_record repeated the load-or-None block and loaded twice in record_refusal

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r5 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-simplicity-r5 · finding [open] (reviewer: in scope) · supervise.py had three identical swallow-and-pass wrappers with redundant local imports

supervise.py had three identical swallow-and-pass wrappers with redundant local imports

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r6 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-simplicity-r6 · finding [open] (reviewer: in scope) · driver_failures double str() and a closure-heavy file_failures

driver_failures double str() and a closure-heavy file_failures

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · fr-wave-driver.md listed a lost push race as transient; it is a StateRefConflict refusal

fr-wave-driver.md listed a lost push race as transient; it is a StateRefConflict refusal

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · 'each pass fetches a repo once' was false on merge-queue paths (_base_now fetched directly)

'each pass fetches a repo once' was false on merge-queue paths (_base_now fetched directly)

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3 created=2026-11-20T13:25:14+00:00 state=open review_scope=in -->
### l-docs-accuracy-r3 · finding [open] (reviewer: in scope) · the signal-stop exit code sentence was imprecise

the signal-stop exit code sentence was imprecise

<!-- fr:journal kind=finding scope=plan id=l-errors-r8 created=2026-11-20T13:25:14+00:00 state=open review_scope=out -->
### l-errors-r8 · finding [open] (reviewer: out of scope) · a failing close-out take-back after a failed dispatch hides the dispatch error and leaves the close-out stuck as started

a failing close-out take-back after a failed dispatch hides the dispatch error and leaves the close-out stuck as started (triage_batch_cmd.py close-out take-back; same code on main).

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: --once/plan mode: an unexpected exception exited 2 (was traceback, exit 1) and printed nothing on an empty message

--once, plan and the cloud pass ledger then re-raise unexpected:* (traceback, exit 1); classify never leaves a message empty (class name fallback). Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: looping and cloud drivers kept no traceback for unexpected:* causes

drive_log.append_traceback writes once per (state dir, cause) per process to host-local drive-tracebacks.log (5 MB rotation); the warning and drive.log line name it. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-errors-r3 -->
### l-errors-r3-resolved · finding [fixed] · resolves l-errors-r3: a bare typer.Exit(2) from _load_state/resolve_state_dir inside a pass became a refusal with an empty message

Shared triage_cmd.fail raises fail_exit at the four sites; a bare Exit gets '<function> exited <code>'. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-errors-r4-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-errors-r4 -->
### l-errors-r4-resolved · finding [fixed] · resolves l-errors-r4: refusals raised through _fail never wrote their reason to drive.log

_stop logs the refusal message even when already printed. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-errors-r5-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-errors-r5 -->
### l-errors-r5-resolved · finding [fixed] · resolves l-errors-r5: the supervisor's Child() OSError killed it with a traceback and recorded nothing; its record/ledger writes failed silently

OSError on spawn records a spawn-failed refusal, refuses, says it and returns 2; _best_effort says each failing write once. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-errors-r6-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-errors-r6 -->
### l-errors-r6-resolved · finding [fixed] · resolves l-errors-r6: trial_conflicts cleanup swallowed failures and its rmtree fallback skipped prune, so a stale registration blocked the probe

New Checkout.prune_worktrees; _clear_scratch rmtree-then-prune before each probe and in cleanup, an unclearable one reported once; the probe removes a worktree it added even with no directory visible. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-errors-r7-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-errors-r7 -->
### l-errors-r7-resolved · finding [fixed] · resolves l-errors-r7: an invalid scope config read in take_lease was transient triage:TriageError instead of an R2 refusal

load_durable and load_scope_config raise ConfigError (a TriageError subclass) on YAML/validation errors; OSError stays transient. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: supervisor process test cleanup could leak a launcher-started supervisor and an unwritten-pid driver forever

Cleanup kills supervisor-* pids first then re-reads drivers until stable; the fake driver has a hard deadline; the err handle is closed. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: a fixed sleep raced the fake driver's SIG_IGN

The driver signals readiness after installing its handler and the test waits on it. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: the R20 swap_issue_labels test passed without the retry

The fake refuses before any removal lands; exactly 2 calls asserted, the second without the undefined label. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: no test moved the PR head or default-branch sha between passes, so a PR-only probe cache would pass

The looping probe test moves rev_parse and head_oid separately and asserts a second trial; unchanged stays one. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-tests-r5 -->
### l-tests-r5-resolved · finding [fixed] · resolves l-tests-r5: no test exercised the old-file drain at a DriveLog rotation

One poll appends two lines, the second rotating; both yielded in order. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-tests-r6-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-tests-r6 -->
### l-tests-r6-resolved · finding [fixed] · resolves l-tests-r6: R17's lockfile case had no trial_conflicts test

test_a_lockfile_conflict_is_resolved_only_when_the_repo_relocks: relock declared -> [], none -> ['uv.lock']. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r1-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-simplicity-r1 -->
### l-simplicity-r1-resolved · finding [fixed] · resolves l-simplicity-r1: three near-identical dedupe-once helpers with inconsistent keys

One _Driver._once backs _stopped_line, _probe_said and _said_once; red and probe keys no longer hold error text. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r2-resolved created=2026-11-20T13:25:14+00:00 state=refuted resolves=l-simplicity-r2 -->
### l-simplicity-r2-resolved · finding [refuted] · resolves l-simplicity-r2: drive_errors derives a cause from traceback frame names; have _fail raise with an explicit cause

Spec R4 (2026-11-19-batch-train-truth-design.md:57) defines the cause as exit:<function>, the function that raised, and the Design (line 100) leaves the pass's helpers, bare typer.Exit included, as they are, covered by R4; ~156 _fail call sites and bare Exits cannot carry a cause argument, and a constant default would merge every ledger cause. The frame walk is the spec's mechanism; 'fail' was added to FAIL_HELPERS for the shared helper.

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r3-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-simplicity-r3 -->
### l-simplicity-r3-resolved · finding [fixed] · resolves l-simplicity-r3: _fail duplicated in triage_drive_cmd and triage_kanban_cmd

One triage_cmd.fail, imported by kanban, drive, claim and batch. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r4-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-simplicity-r4 -->
### l-simplicity-r4-resolved · finding [fixed] · resolves l-simplicity-r4: driver_record repeated the load-or-None block and loaded twice in record_refusal

_old(state_dir) and _current(old); record_refusal loads once. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r5-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-simplicity-r5 -->
### l-simplicity-r5-resolved · finding [fixed] · resolves l-simplicity-r5: supervise.py had three identical swallow-and-pass wrappers with redundant local imports

One _best_effort helper; the local imports are gone. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-simplicity-r6-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-simplicity-r6 -->
### l-simplicity-r6-resolved · finding [fixed] · resolves l-simplicity-r6: driver_failures double str() and a closure-heavy file_failures

_view_state returns str (the double conversion is gone). The planner/applier split was declined: dry-run and write already share one path via the write guards, and the action depends on a mid-way forge read (view_issue), so the split would not be simpler. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: fr-wave-driver.md listed a lost push race as transient; it is a StateRefConflict refusal

The transient example is a push the remote refused (a permission or a hook); the lost race stays a refusal. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: 'each pass fetches a repo once' was false on merge-queue paths (_base_now fetched directly)

Code fixed per R19: _base_now goes through _fetched_reader/_fetch_once, tested for one fetch and a remembered failure; the claim now holds. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3-resolved created=2026-11-20T13:25:14+00:00 state=fixed resolves=l-docs-accuracy-r3 -->
### l-docs-accuracy-r3-resolved · finding [fixed] · resolves l-docs-accuracy-r3: the signal-stop exit code sentence was imprecise

A signalled or orphaned supervisor exits 0; otherwise it exits with the driver's code (130 after an interrupt or SIGTERM stop). The duplicated reviewed note was removed too. Commits 689ab1306, dcdf75d90, 4f29ad692, 1adf7a983, 51122abb3; scoped run 5170 passed (lens-fix.log).

<!-- fr:journal kind=finding scope=plan id=l-errors-r8-resolved created=2026-11-20T13:25:14+00:00 state=open resolves=l-errors-r8 out_of_scope=true -->
### l-errors-r8-resolved · finding [out-of-scope] · resolves l-errors-r8: a failing close-out take-back after a failed dispatch hides the dispatch error and leaves the close-out stuck as started

Predates this change: the same take-back code is on main (triage_batch_cmd.py ~6575, ~6650). Filed as derio-net/super-fr#1601.
