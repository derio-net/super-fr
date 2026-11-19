# Merge-train truth: a driver that survives its own failures, sees red and conflicting drafts, and fetches once

Batch `train-truth` (derio-net/super-fr#1491, #1492, #1493, #1540, #1541, #1543), one PR.

## Background

`fr triage batch drive --yes` is meant to run a backlog's waves to completion unattended. The
operator's direction (spec journal decision `d-resident-orchestrator`) is that the driver will be
owned by a resident orchestrator agent session, the way the gates are: the session starts the
driver, always knows whether it is running, spends no tokens while it runs well, and the driver
and anything supervising it end when that session ends.

Today the driver ends on almost any failure. `_Driver` (`packages/fr/src/fr/commands/triage_batch_cmd.py:3795`)
handles errors the way a one-shot command does: about 30 call sites inside it call `_fail()`
(imported at :85 from `fr.commands.triage_kanban_cmd`, defined there at :93), which raises
`typer.Exit` (click's `Exit`, a `RuntimeError`, not a `SystemExit`). Module-level helpers the pass
calls do the same, e.g. `dispatch_batch` (:1817; `_fail` at :1852-:2000). The host loop
`_host_loop` (:7237) has one error boundary, `ForgeReadError` (gh#910), around `one_pass` only; the
pacing waits and `wait_out`'s lease renewals (:3516, :3527) sit outside it. `save_pass` (:4002)
catches every `TriageError` and calls `_fail`, so a `StateRefPushRefused`
(`fr/triage/state_ref.py:89`, "nothing on the remote moved") ends a loop that one more pass would
have healed (#1491, observed four times on 2026-11-17). The cloud entry `fr triage drive pass`
(`commands/triage_drive_cmd.py:445`, :581-600) calls `take_lease` and `one_pass` directly and also
catches only `ForgeReadError`. Earlier fixes (#910, #921, #998) each moved one call site inside the
boundary; the shape stayed. A restart is already safe, because recovery is decided from the
recorded events (the 2026-11-15 manual restart resumed with nothing lost), so an in-process retry of
a pass is no less safe than a restart.

The merge train looks at a batch PR's CI and conflicts only when the PR is a train member, and an
unapproved draft is not one: `_walk_queue` (`fr/triage/batch_drive.py:1509`, filter :1533) and
`_walk_merge_train` (:1610, filter :1632) skip it with `if pr is None or pr.state != "OPEN" or
(pr.draft and not approved): continue`, and return no `Train` when no member is left (:1537,
:1672). Batch sessions deliver drafts, so red CI on a delivered batch is never handed back (#1492),
and a conflict is found only when an approved PR heads the train and the merge's update fails
(`batch_merge._update` :625, `MergeConflictError` :63, raised :638), after the operator approved it
(#1493). In `batch_drive.py`, `conflicting()` (`fr/triage/mergeability.py:13`) is used only for
collected close-outs (:1138). The per-pass PR read (`_Driver` :4283-4303, `client.pr_view`)
already returns `mergeable` and `merge_state` (`real_ghclient.py:416-442`,
`real_ghrestclient.py:772-788`), and `LivePr` (`batch_drive.py:150-174`) has both fields, but that
read leaves them empty.

`_fetched_reader` (`triage_batch_cmd.py:4822`) lets `checkout.fetch()` raise and records the repo
as fetched only on success, so a pass may fetch a failing repo again (#1540); its callers catch
`TriageError` (`GitError` is one, `fr/triage/gitseam.py:35`) and degrade locally (e.g. `_ci_none`
:4842-4847). `swap_issue_labels` (`fr/gh.py:407`) retries a refused call after dropping a
`'<label>' not found` removal; its docstring rests on an unverified claim about gh's label
resolution, though the retry is idempotent either way (#1541). `batch cancel --yes`
(`triage_batch_cmd.py:920`) applies the gh#803 tracking gate (:956), which needs `--checkout`, to a
batch that was never dispatched, although only dispatch writes the `fr:in-progress` label and the
marker comment that cancel withdraws (#1543).

## Requirements

R1. Inside a looping `fr triage batch drive --yes` (no `--once`), no failure raised during a pass, a pacing wait or a lease renewal ends the process directly: every failure is either a driver refusal or a transient failure, decided at one boundary that wraps the loop's whole iteration.
R2. A driver refusal is a failure only the operator can fix: an unsupported forge operation, an invalid repo or triage config, a runner that refuses or does not take run-unit work, `StateRefConflict` (another writer moved the state ref), `LeaseHeld` (another driver holds the scope), `LeaseExpired` (an expired lease only the operator may take, resumed with `fr triage lease take --yes`), a privacy guard refusal and the single-pass guard. Each refusal carries a stable cause id, the command that resumes the driver once it is fixed, and the exit code it ends with (2).
R3. A transient failure is every other failure in a pass: `StateRefPushRefused`, a git error, any other `TriageError` and any unexpected exception. It ends the pass, keeps the durable state local, is reported once per cause, and the next pass starts after a backoff that begins at `--interval` and doubles per consecutive failed pass up to 15 minutes (or `--interval`, when that is longer). A pass that ends cleanly resets the backoff and the report memory. A rate limit keeps its own budget-reset wait. A transient failure carries the exit code its call site exits with today (2, or 1 where the site used `code=1`, such as a failed dispatch).
R4. A `typer.Exit` that reaches the boundary from a helper the pass calls is classified by its exit code: 2 is a refusal (cause `exit:<function>`, the function that raised it), any other code a transient failure.
R5. After 10 consecutive failed passes the driver stops as a refusal whose cause is the last failure's.
R6. `--once`, plan mode (no `--yes`) and the cloud entry `fr triage drive pass` keep today's exit code for every failure, taken from the failure's carried code; the cloud entry still writes the outbox it has before it exits on a refusal or transient failure.
R7. A tripwire test fails when a `_fail(...)` call or a `raise typer.Exit` appears lexically inside a `_Driver` method, `one_pass`, `_host_loop` or `wait_out`; the loop's deliberate ends (`--once` done or waiting, stalled, restart) leave `_host_loop` as a returned value that `batch_drive_command` turns into the exit code.
R8. On a refusal the looping driver records the refusal (cause id, message, time, fr version, resume command) in the scope's state directory, renders the board once, and exits 2, keeping its lease as today. Needs you now on the board shows the stopped driver with its reason and resume command while the recorded refusal is newer than the lease's last pass.
R9. Every refusal, every transient failure and every supervised crash is counted per cause in a durable driver-failure ledger in the scope's state directory: per cause its kind (refusal, transient, crash), count, first and last seen, last message, fr version, and the tracking issue once one is filed. The ledger and the driver record are host-local: neither rides on the state ref.
R10. `fr triage drive failures` lists the ledger, most frequent cause first. With `--file --yes` it files one issue per cause that has none, in the scope's state repo when it has one, else in the scope's repo for a single-repo scope, and refuses for an org or group scope with no state repo; that target repo's `forge.issues` and `tracking` settings gate it (under `off`/`none` it files nothing and says so). The issue carries label `fr:driver-failure`, a hidden marker `fr-driver-failure:<cause>`, the cause, kind, counts, dates, fr version and the exception class, never the failure message text. It comments the new count on a cause's open issue when the count grew since the last filing, and files a new issue naming the closed one when a cause recurs after its issue closed; it records each issue in the ledger. A refusal's exit output and its board need name this command, so the owning agent turns every recurring cause into tracked improvement work and real refusals trend to zero.
R11. `fr triage batch drive --supervise --yes` (loop mode only; refused with `--once` or without `--yes`) runs a supervisor that takes neither `drive.lock` nor the lease and starts the driver as its child, through the interpreter (`fr_argv`), with the same arguments less `--supervise`. It restarts the child when it ends other than deliberately. A deliberate end is exit 0, 2 or 3, or the child's own clean stop on SIGINT, SIGTERM or SIGHUP; anything else (another exit code, or death by another signal, such as SIGKILL) is a crash. Restarts back off from 5 s, doubling to 5 minutes; a sixth restart within 30 minutes stops the supervisor as a refusal (cause `crash-loop`, exit 2), recorded as R8 says.
R12. The supervisor never detaches: it stays in its caller's session and process group. When its parent process dies (its parent pid changes) or it gets SIGHUP, SIGINT or SIGTERM, it sends SIGTERM to its driver child, then SIGKILL after 10 s if the child is still alive, and exits. A supervised driver checks between passes and during its waits that its supervisor is still its parent, and stops cleanly, releasing its lease, when it is not.
R13. The supervisor exits with its driver's deliberate exit code. Each restart is recorded in the ledger (cause `crash:<signal or exit code>`) and on the scope's driver record (supervisor pid, restart count, last crash).
R14. `fr triage drive status` (read-only) reports whether a driver holds the scope: its pid and whether it is alive on this host, whether it is supervised and by which pid, restarts, last pass time and the last recorded refusal. It exits 0 when a live driver holds the scope and 3 when none does.
R15. Each pass, every open batch PR whose checks are failing, draft or ready, approved or not, gets the existing red recovery (`red_decision`: an idle session is handed the failure, a working one is waited on, an absent or done one is a Needs you now entry), with the `RED_HANDBACKS_PER_DISPATCH` cap counted across draft and ready hand-backs. Merge gating is unchanged: an unapproved draft never merges and the driver never readies or approves it.
R16. A batch PR with failing checks is never shown as awaiting approval: the board lists it as failing with its hand-back state, and the repo's train line lists it among the stepped-over PRs, a train being reported whenever the repo has a member or a red or conflicting non-member.
R17. Each pass, every open batch PR whose forge `mergeable` is `CONFLICTING` or whose merge state is `DIRTY`, draft or ready, approved or not, other than the train's merge candidate, is trial-merged with the default branch in a scratch worktree that is always removed, under the merge's own resolution rules (a version file whose PR change is the version alone, and a lockfile when the repo relocks, are resolved, not conflicts). A trial merge is made at most once per (PR, head, default-branch sha) per driver process. A real conflict is handed to an idle session with the existing conflict brief and recorded as a `conflict` event at that head (`delivered: session`); a working or unknown session is waited on (nothing recorded, tried again next pass); an absent or done session gets a `conflict` event with `delivered: held`, which the board shows under Needs you now as a merge conflict. `conflict_decision`'s skip, wait-behind and `HANDBACKS_PER_DISPATCH` rules apply. The probe writes no merge stop, adds no forge read beyond the one `pr_view` per open batch PR per pass, and trial-merges no PR the forge reports clean; the approved merge candidate's path is unchanged.
R18. A batch PR with a `conflict` event at its current head is never asked for approval: a delivered one shows on its board card as conflicting and handed back, and a held one keeps the existing merge-conflict need, so one PR never has two rows.
R19. Within one pass, `_fetched_reader` fetches each repo at most once, whether the fetch succeeded or failed; a failed fetch is recorded for the pass and every later read of that repo in the pass raises the same `GitError` again without fetching, so each caller's existing handler decides the outcome.
R20. `swap_issue_labels`'s docstring states that its correctness does not depend on whether gh resolves every label before it mutates, and a unit test proves that a refused call that applied part of its change, followed by the retry, ends with exactly the wanted labels.
R21. `fr triage batch cancel --yes` of a batch with no `dispatch` event removes no label, posts no withdrawal comment, applies no tracking gate and needs no `--checkout`; it still releases this scope's claims and writes the cancel event. A dispatched batch keeps today's behaviour.
R22. A looping driver and its supervisor append every line they print to `drive.log` in the scope's state directory, each prefixed with a UTC timestamp and a kind (`pass`, `action`, `transient`, `refusal`, `restart`, `stop`); the file rotates at 5 MB, keeping one previous file. `fr triage drive log [-n N] [-f]` (read-only) prints the last N lines (default 50) and with `-f` follows the file as it grows, across a rotation, until interrupted.
R23. The Batches board (`board.html`) shows an Activity panel with the newest 50 `drive.log` entries, newest first, re-rendered with the board on every pass; with no log it says no driver has run.
R24. The `fr-triage` skill's driver section and the wave-driver explainer describe the pass boundary, the supervisor and its lifetime, `fr triage drive status`, the failure ledger and `fr triage drive failures`, the activity log and `fr triage drive log`, and the early red and conflict hand-backs.

## Design

### A. The pass boundary (R1–R7)

A new module `fr/triage/drive_errors.py` holds the vocabulary:

- `DriverRefusal(Exception)` with `cause`, `message`, `resume`, `code = 2`.
- `TransientPassFailure(Exception)` with `cause`, `message`, `code` (2 by default), wrapping the
  original.
- `classify(exc) -> DriverRefusal | TransientPassFailure`: the R2 classes map to refusals
  (`StateRefConflict`, `LeaseHeld`, `LeaseExpired`, `UnsupportedForgeOperation`, the privacy guard's
  refusal and the config errors by class); a click `Exit` maps per R4, its function name taken from
  the innermost traceback frame in `fr`; everything else is transient, cause `push-refused`,
  `git:<op>`, `triage:<class>` or `unexpected:<class>`. Causes never include message text (messages
  carry heads and paths).

Inside `_Driver`, every `_fail(...)` becomes `raise DriverRefusal(...)` (the R2 classes) or
`raise TransientPassFailure(..., code=1)` where the site used `code=1`, or is removed so the
original exception propagates. `save_pass` stops catching `TriageError` wholesale: a
`StateRefPushRefused` propagates (transient), a `StateRefConflict` is a refusal. `take_lease`
raises `LeaseHeld`/`LeaseExpired` as refusals instead of `_fail`. Module-level helpers
(`dispatch_batch` and the others the pass calls) are left as they are and covered by R4.

`one_pass` stays the single body. `_host_loop`'s whole iteration (pacing wait, `wait_out`, renewal,
`one_pass`) runs inside one `try`; the handler classifies, reports, records (R8, R9), backs off or
stops. `KeyboardInterrupt` passes through untouched. The loop's deliberate ends return a
`LoopEnd(code, restart_to)` that `batch_drive_command` converts into `typer.Exit` or the gh#998
restart; in `--once` or plan mode the handler returns a `LoopEnd` with the failure's code at once
(R6). `batch_drive_command` keeps its lease rule: a code-2 end keeps the lease, any other releases
it. The backoff state lives on the loop, never in the state directory.

`drive_pass_command` (the cloud entry) wraps its lease-and-pass block the same way: it writes the
outbox it has (`_write_outbox(outbox, driver.outbox())`), prints the failure, and exits with its
carried code; its rate-limit branch is unchanged.

Tripwire (R7): `tests/unit/test_tripwire_drive_pass_boundary.py` parses `triage_batch_cmd.py` with
`ast` and fails on a `_fail` call or `raise typer.Exit` inside `class _Driver`, `one_pass`,
`_host_loop` or `wait_out`. A behavioural test drives a pass whose `dispatch_batch` `_fail`s
(code 2 and code 1) and asserts the refusal/transient classification.

### B. Driver record, failure ledger and the improvement loop (R8–R10)

Two host-local files in the scope's state directory, written atomically (`write_text_atomic`), not
named in `state_ref.REF_FILES` (state_ref.py:53-69), so neither rides on the ref; the ref module's
docstring gains a line naming them beside `scope.yaml`:

- `driver.yaml`: pid, started, supervised (supervisor pid), restarts, last crash, last refusal
  `{cause, message, at, fr_version, resume}`.
- `driver-failures.yaml`: the ledger, `schema: 1`, `causes: {<cause>: {kind, count, first, last,
  message, fr_version, issue, filed_count}}`.

Neither is a registered artifact kind: the triage state directory is never committed by default.
On a refusal the handler writes both, renders the board (the pass's own render path) and returns
`LoopEnd(2)`. `views.needs_you` (views.py:277) adds a `driver-stopped` need when `driver.yaml`'s
`last_refusal.at` is newer than the lease's `last_pass`.

`fr triage drive failures` is a new verb on the existing `drive` group
(`commands/triage_drive_cmd.py:64`). `--file --yes` writes only through the target repo's
`GhClient` adapter (§3.J), creating the `fr:driver-failure` label lazily and de-duplicating by the
marker. The refusal's stderr line and the `driver-stopped` need both end with
`fr triage drive failures --file --yes`.

### C. The session-bound supervisor (R11–R14)

`fr/triage/supervise.py` is pure policy plus a thin process seam:

- `restart_decision(history, now, end) -> stop | restart(delay) | crash-loop`, where `end` is an
  exit code or a signal.
- `Supervisor.run(argv)`: `subprocess.Popen(fr_argv(*args, "--supervised-by", str(os.getpid())))`
  with no `start_new_session`; waits on the child and polls `os.getppid()` every second;
  SIGHUP/SIGINT/SIGTERM handlers forward SIGTERM and escalate to SIGKILL after 10 s. It appends its
  own lines to `drive.log` (§E) and updates `driver.yaml`.

`--supervised-by <pid>` (hidden) makes the driver record `supervised` in `driver.yaml` and check
`os.getppid() == pid` between passes and inside the module-level `_sleep` (:3465) and `wait_out`
(:3516); a mismatch is a clean stop (lease released, exit 0). The child's own SIGTERM handling
(`_sigterm_interrupts`, :7215) already makes a signal to the child a clean stop, which the
supervisor reads as deliberate (R11). The gh#998 self-restart (`_exec`, `os.execve`) keeps the
child's pid, so the supervisor still sees it.

`fr triage drive status` reads `driver.yaml` and the lease, probes the pid with `os.kill(pid, 0)`
when the lease's host id is this host's, and prints one block.

How the owning agent knows the driver is running: it starts `drive --supervise --yes` as a
background command; the harness tells it when that command exits, which happens only on done,
refusal, stall or crash loop. Between those ends it spends nothing; `fr triage drive status` answers
on demand.

### D. Red and conflicting drafts (R15–R18)

The driver's per-pass read (`_Driver` :4293) fills `LivePr.mergeable`/`merge_state` from the
`pr_view` it already makes. `views.drive_snapshot` (facts only) leaves them empty, as now.

Both walks split the member filter. An OPEN PR that is a non-member only because it is an
unapproved draft still gets (a) the failing-checks branch, which appends it to `stepped` and emits
the existing `warn` action with `red=True`, and (b) a `conflict-probe` action when
`conflicting(pr.mergeable, pr.merge_state)`. Neither makes it a member, a merge candidate or a
stop. A member that is not the merge candidate this pass and reads conflicting also gets the
`conflict-probe`. A `Train` is returned when the repo has a member or any red or conflicting
non-member (head `None` when no member).

`_act` handles `conflict-probe` through `_Driver._probe_conflict`: it skips a (PR, head, base sha)
already probed by this process; otherwise it runs `batch_merge.trial_conflicts(checkout, main,
version, pr_head) -> list[str]`, the `_update` merge step and `_unresolvable` factored out, with the
merge aborted and the scratch worktree removed. It needs only the fetched clone and the repo's
version config, so it builds no merge context and reads no merge methods or rules. An empty list
is a no-op. A non-empty one goes through `conflict_decision` (skip, wait-behind, held cap) and then
by session status: idle → the existing `_hand_back` message path (never `_fresh_conflict`);
working or unknown → wait; absent or done → a `conflict` event `delivered: held`. It writes no
merge stop.

The board (`views.needs_you`) skips `approve-pr` for a PR whose batch has a `conflict` event at
the PR's head; a held one is already the `merge-conflict` need (views.py:405-414), a delivered one
is a card hint `conflicting — handed back`. Failing PRs are already excluded from `approve-pr`
(not green, views.py:308) and keep the `failing-ci`/`red-pr` needs.

### E. The activity log (R22–R23)

`fr/triage/drive_log.py`: `DriveLog(state_dir)` with `append(kind, line, now)` (open-append-close
per line, so a crash loses no earlier line; rotate to `drive.log.1` before a write that would pass
5 MB), `tail(n)` and `follow()` (poll every second; on a size shrink or inode change reopen, which
follows a rotation). The driver's `_say` and its failure reports go through one `_emit(kind, line)`
that prints AND appends when a log is attached (loop mode with `--yes` only; plan mode and `--once`
attach none, so their output is unchanged). The supervisor appends its `restart`/`stop` lines to
the same file. The board renderer reads `tail(50)` into an Activity panel (the existing
`components.py` tokens; long lines wrap at phone width). The file is operator-facing only: nothing
reads it to decide anything, and it does not ride on the state ref. `fr triage drive log` is a
verb on the `drive` group.

### F. Small fixes (R19–R21)

- `_fetched_reader`: `self._fetch_failed: dict[str, GitError]`, reset per pass with `_fetched`; on
  a recorded failure raise it again; on a new failure record it and re-raise.
- `swap_issue_labels`: docstring only, plus a unit test whose fake `_run_gh` applies the add and
  then refuses the removal.
- `batch cancel`: `dispatched = any(e.kind == "dispatch" for e in batch.events)`; when it is false,
  `withdraws` is empty and the tracking gate is skipped; claim release (`execute(env, …)`) runs as
  before.

## Verification

strategy: none
gate: developer

- drive-pass-boundary: none — CI tests drive `_host_loop` and `drive pass` with a fake remote refusing one push and a pass raising each failure class (including a helper's `_fail`); the AST tripwire pins the boundary
- drive-failure-ledger: none — CI tests over the ledger writer, the board need and `drive failures --file` against a fake GhClient
- drive-session-supervisor: none — CI integration tests run a real supervisor and child process, SIGKILL the child and kill the parent
- drive-red-drafts: none — CI unit tests on both walks and `_recover` with fake sessions (idle, working, done)
- drive-conflict-early: none — CI tests with a fake forge reporting CONFLICTING and a scratch git repo for the trial merge
- drive-fetch-once: none — CI unit test counting fetches on a fake checkout that fails
- swap-labels-retry-converges: none — CI unit test with a fake `_run_gh` that applies part of a call, then refuses
- cancel-undispatched-no-checkout: none — CI CLI test of `batch cancel --yes` with no `--checkout` on a never-dispatched batch
- drive-activity-log: none — CI tests on `DriveLog` (append, rotate, follow across a rotation) and the board panel render

Every requirement is proven by unit and integration tests in CI with fakes. The first
resident-orchestrator drive is its own future work.

## Out of scope

- The resident orchestrator agent itself (what it does on a wake).
- #1216 (one scope-owned writer for drive and page refresh): `StateRefConflict` stays a refusal.
- launchd/systemd units: the supervisor is session-bound by design.
- Converting module-level helpers' `_fail` into typed errors: R4 classifies them at the boundary.
