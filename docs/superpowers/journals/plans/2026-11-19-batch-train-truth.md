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
