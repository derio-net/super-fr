# Merge-train truth: a driver that survives its own failures, sees red and conflicting drafts, and fetches once

Batch `train-truth` (derio-net/super-fr#1491, #1492, #1493, #1540, #1541, #1543), one PR.

## Background

`fr triage batch drive --yes` is meant to run a backlog's waves to completion unattended. The
operator's direction (spec journal decision `d-resident-orchestrator`) is that the driver will be
owned by a resident orchestrator agent session, the way the gates are: the session starts the
driver, always knows whether it is running, spends no tokens while it runs well, and the driver
and anything supervising it end when that session ends.

Today the driver ends on almost any failure. `_Driver` (`packages/fr/src/fr/commands/triage_batch_cmd.py`)
handles errors the way a one-shot command does: about 31 call sites inside a pass call
`_fail()` (imported from `fr.commands.triage_kanban_cmd`), which raises `typer.Exit` and ends the
process. The host loop `_host_loop` (~:7224) has one error boundary, `ForgeReadError` (gh#910).
`save_pass` (~:4002) catches every `TriageError` and calls `_fail`, so a `StateRefPushRefused`
(`fr/triage/state_ref.py:89`, "nothing on the remote moved") ends a loop that one more pass would
have healed (#1491, observed four times on 2026-11-17). Earlier fixes (#910, #921, #998) each moved
one call site inside the boundary; the shape stayed. A restart is already safe, because recovery
is decided from the recorded events (the 2026-11-15 manual restart resumed with nothing lost), so
an in-process retry of a pass is no less safe than a restart.

The merge train looks at a batch PR's CI and conflicts only when the PR is a train member, and an
unapproved draft is not one: `_walk_queue` (`fr/triage/batch_drive.py` ~:1533) and
`_walk_merge_train` (~:1632) skip it with `if pr is None or pr.state != "OPEN" or (pr.draft and not
approved): continue`. Batch sessions deliver drafts, so red CI on a delivered batch is never handed
back (#1492), and a conflict is found only when an approved PR heads the train and the merge's
update fails (`batch_merge._update` ~:633, `MergeConflictError`), after the operator approved it
(#1493). `conflicting()` (`fr/triage/mergeability.py:13`) is used only for collected close-outs
(`batch_drive.py` ~:1138). The per-pass PR read (`_Driver` ~:4283, `client.pr_view`) already
returns `mergeable` and `mergeStateStatus` (`real_ghclient.py:416`), but `LivePr` built there
drops them.

`_fetched_reader` (`triage_batch_cmd.py` ~:4822) lets `checkout.fetch()` raise and records the
repo as fetched only on success, so a pass may fetch a failing repo again (#1540).
`swap_issue_labels` (`fr/gh.py` ~:406) retries a refused call after dropping a `'<label>' not
found` removal; its docstring rests on an unverified claim about gh's label resolution, though the
retry is idempotent either way (#1541). `batch cancel --yes` (`triage_batch_cmd.py` ~:930) applies
the gh#803 tracking gate, which needs `--checkout`, to a batch that was never dispatched, although
only dispatch writes the `fr:in-progress` label and the marker comment that cancel withdraws (#1543).

## Requirements

R1. Inside a looping `fr triage batch drive --yes` (no `--once`), no failure raised during a pass ends the process directly: every failure is either a driver refusal or a transient failure.
R2. A driver refusal is a failure only the operator can fix: an unsupported forge operation, an invalid repo or triage config, a runner that refuses or does not take run-unit work, a `StateRefConflict` (another writer moved the state ref), a privacy guard refusal and the single-pass guard. Each refusal carries a stable cause id and the command that resumes the driver once it is fixed.
R3. A transient failure is every other failure in a pass: `StateRefPushRefused`, a git error, any other `TriageError` and any unexpected exception. It ends the pass, keeps the durable state local, is reported once per cause, and the next pass starts after a backoff that begins at `--interval` and doubles per consecutive failed pass up to 15 minutes (or `--interval`, when that is longer). A pass that ends cleanly resets the backoff and the report memory. A rate limit keeps its own budget-reset wait.
R4. After 10 consecutive failed passes the driver stops as a refusal whose cause is the last failure's.
R5. `--once` and plan mode (no `--yes`) keep today's exit codes for every failure.
R6. A tripwire test fails when a `_fail(...)` call or a `raise typer.Exit` appears lexically inside a `_Driver` method, `one_pass` or `_host_loop`.
R7. On a refusal the looping driver records the refusal (cause id, message, time, fr version, resume command) in the scope's state directory and exits 2. Needs you now on the board shows the stopped driver with its reason and resume command until a driver holds the scope again.
R8. Every refusal, every transient failure and every supervised crash is counted per cause in a durable driver-failure ledger in the scope's state directory: per cause its kind (refusal, transient, crash), count, first and last seen, last message, fr version, and the tracking issue once one is filed.
R9. `fr triage batch drive failures` lists the ledger, most frequent cause first. With `--file --yes` it files one forge issue per cause that has none (label `fr:driver-failure`, a hidden marker `fr-driver-failure:<cause>`, the counts and last message in the body), comments the new count on a cause's open issue when the count grew since the last filing, and files a new issue naming the closed one when a cause recurs after its issue closed. It records each issue in the ledger. It files nothing under `forge.issues: off` or `tracking: none`, and says so. A refusal's exit output and its board need name this command, so the owning agent turns every recurring cause into tracked improvement work and real refusals trend to zero.
R10. `fr triage batch drive --supervise --yes` (loop mode only; refused with `--once` or without `--yes`) runs a supervisor that starts the driver as its child with the same arguments and restarts it when it ends other than deliberately. Deliberate ends are exit 0 (done), 2 (refusal), 3 (stalled) and an operator stop (SIGINT or SIGTERM to the supervisor). Restarts back off from 5 s, doubling to 5 minutes; a sixth restart within 30 minutes stops the supervisor as a refusal (cause `crash-loop`), recorded as R7 says.
R11. The supervisor never detaches: it stays in its caller's session and process group. When its parent process dies (its parent pid changes) or it gets SIGHUP, SIGINT or SIGTERM, it sends SIGTERM to its driver child, then SIGKILL after 10 s if the child is still alive, and exits. A supervised driver checks between passes and during its sleeps that its supervisor is still its parent, and stops cleanly, releasing its lease, when it is not.
R12. The supervisor exits with its driver's deliberate exit code. Each restart is recorded in the ledger (cause `crash:<signal or exit code>`) and on the scope's driver record (supervisor pid, restart count, last crash).
R13. `fr triage batch drive status` (read-only) reports whether a driver holds the scope: its pid and whether it is alive, whether it is supervised and by which pid, restarts, last pass time and the last recorded refusal. It exits 0 when a live driver holds the scope and 3 when none does.
R14. Each pass, every open batch PR whose checks are failing, draft or ready, approved or not, gets the existing red recovery (`red_decision`: an idle session is handed the failure, a working one is waited on, an absent or done one is a Needs you now entry), with the `RED_HANDBACKS_PER_DISPATCH` cap counted across draft and ready hand-backs. Merge gating is unchanged: an unapproved draft never merges and the driver never readies or approves it.
R15. A batch PR with failing checks is never shown as awaiting approval: the board lists it as failing with its hand-back state, and the train line reports it among the stepped-over PRs.
R16. Each pass, every open batch PR whose forge `mergeable` is `CONFLICTING` or whose merge state is `DIRTY`, draft or ready, approved or not, is trial-merged with the default branch in a scratch worktree under the merge's own resolution rules (a version file whose PR change is the version alone, and a lockfile when the repo relocks, are resolved, not conflicts). A real conflict gets the existing conflict hand-back (`conflict_decision`: one `conflict` event per head, wait-behind on a shared path, `HANDBACKS_PER_DISPATCH`, idle sessions only). The forge read stays the one `pr_view` per open batch PR per pass, no PR the forge reports clean is trial-merged, and the approved head-of-train path is unchanged.
R17. A batch PR with a recorded `conflict` event at its current head is shown on the board as conflicting with its hand-back state, never asked for approval.
R18. Within one pass, `_fetched_reader` fetches each repo at most once, whether the fetch succeeded or failed; a failed fetch is recorded for the pass and every later read of that repo in the pass raises the same failure as a transient failure without fetching again.
R19. `swap_issue_labels`'s docstring states that its correctness does not depend on whether gh resolves every label before it mutates, and a unit test proves that a refused call that applied part of its change, followed by the retry, ends with exactly the wanted labels.
R20. `fr triage batch cancel --yes` of a batch with no `dispatch` event removes no label, posts no withdrawal comment, applies no tracking gate and needs no `--checkout`; it still releases this scope's claims and writes the cancel event. A dispatched batch keeps today's behaviour.
R21. The `fr-triage` skill's driver section and the wave-driver explainer describe the pass boundary, the supervisor and its lifetime, `drive status`, the failure ledger and `drive failures`, the activity log and `drive log`, and the early red and conflict hand-backs.
R22. A looping driver and its supervisor append every line they print to `drive.log` in the scope's state directory, each prefixed with a UTC timestamp and a kind (`pass`, `action`, `transient`, `refusal`, `restart`, `stop`); the file rotates at 5 MB, keeping one previous file. `fr triage batch drive log [-n N] [-f]` (read-only) prints the last N lines (default 50) and with `-f` follows the file as it grows, across a rotation, until interrupted.
R23. The Batches board (`board.html`) shows an Activity panel with the newest 50 `drive.log` entries, newest first, re-rendered with the board on every pass; with no log it says no driver has run.

## Design

### A. The pass boundary (R1–R6)

A new module `fr/triage/drive_errors.py` holds the vocabulary:

- `DriverRefusal(Exception)` with `cause: str`, `message: str`, `resume: str`.
- `TransientPassFailure(Exception)` with `cause: str`, `message: str`, wrapping the original.
- `cause_of(exc) -> str`: a stable id from the exception class and the call site's label, never
  from the message text (messages carry heads and paths): `push-refused`, `git:<op>`,
  `triage:<site>`, `unexpected:<ExceptionClass>`.

Inside `_Driver`, every `_fail(...)` becomes `raise DriverRefusal(...)` (the R2 classes) or is
removed so the original exception propagates (transient). A single helper
`_refuse(cause, message, resume)` replaces the sites; `save_pass` stops catching `TriageError`
wholesale and lets `StateRefPushRefused` propagate as transient while `StateRefConflict` becomes a
refusal.

`one_pass` stays the single body. The boundary lives in `_host_loop`: it catches `DriverRefusal`,
`TransientPassFailure`, `ForgeReadError` (kept as is) and every other `Exception` (wrapped as
transient). `KeyboardInterrupt` and `SystemExit` pass through untouched. In `--once` or plan mode
the boundary re-raises through `_fail` with today's code (R5): the CLI wrapper `batch_drive_command`
converts a `DriverRefusal` into exit 2 and any other failure into the exit it gets today. The
backoff state (`consecutive`, next delay) lives on the loop, never in the state directory.

The cloud entry (`fr triage drive pass`) runs one pass per wake and keeps its exit codes; the
boundary classes are what it reports, unchanged otherwise.

Tripwire (R6): `tests/unit/test_tripwire_drive_pass_boundary.py` parses `triage_batch_cmd.py` with
`ast` and fails on a `_fail` call or `raise typer.Exit` inside `class _Driver`, `one_pass` or
`_host_loop`.

### B. Refusal record, failure ledger and the improvement loop (R7–R9)

Two files in the scope's state directory, written atomically (`write_text_atomic`), carried by the
state ref like the rest of the durable state:

- `driver.yaml`: the current driver record: pid, host id, started, supervised (supervisor pid),
  restarts, last crash, last refusal `{cause, message, at, fr_version, resume}`. A driver that takes
  the lease clears `last_refusal`.
- `driver-failures.yaml`: the ledger, `schema: 1`, `causes: {<cause>: {kind, count, first, last,
  message, fr_version, issue, filed_count}}`.

Neither is a registered artifact kind: both live in the triage state directory, which is never
committed to a product repo by default (like `judgements.yaml`'s cache copy). The board's Needs you
now gets a `driver-stopped` need from `driver.yaml` when `last_refusal` is set and no live lease
holds the scope.

`drive failures` reads the ledger. `--file --yes` writes through the scope's `GhClient` adapter
only (triage batch rule §3.J), creating the `fr:driver-failure` label lazily, de-duplicating by the
marker. The refusal's stderr line and the `driver-stopped` need both end with
`fr triage batch drive failures --file --yes`.

### C. The session-bound supervisor (R10–R13)

`fr/triage/supervise.py` is pure policy plus a thin process seam:

- `restart_decision(history, now, code_or_signal) -> stop | restart(delay) | crash-loop`.
- `Supervisor.run(argv)`: `subprocess.Popen(argv + ["--supervised-by", str(os.getpid())])` with no
  `start_new_session`; a loop that waits on the child and polls `os.getppid()` every second;
  SIGHUP/SIGINT/SIGTERM handlers that forward SIGTERM and escalate to SIGKILL after 10 s.

`--supervised-by <pid>` (hidden) makes the driver record `supervised` in `driver.yaml` and check
`os.getppid() == pid` between passes and inside `_sleep`/`wait_out`; a mismatch is an operator
stop (lease released, exit 0 — the supervisor is gone, so nobody reads the code). The gh#998
self-restart (`_exec`) replaces the child in place, so the supervisor still sees its child pid.

`drive status` reads `driver.yaml` and the lease, probes the pid with `os.kill(pid, 0)` on the same
host id, and prints one block. It is read-only and needs no `--yes`.

How the owning agent knows the driver is running: it starts `drive --supervise --yes` as a
background command; the harness tells it when that command exits, which happens only on done,
refusal, stall or crash loop. Between those ends it spends nothing; `drive status` answers on
demand.

### D. Red and conflicting drafts (R14–R17)

`LivePr` gains no new fields (it already has `mergeable` and `merge_state`); the driver's per-pass
read (`_Driver` ~:4293) fills them from the `pr_view` it already makes. `views.drive_snapshot`
(facts only) leaves them empty, as now.

Both walks (`_walk_queue`, `_walk_merge_train`) split the member filter: an OPEN PR that is a
non-member only because it is an unapproved draft still gets (a) the failing-checks branch, which
emits the existing `warn` action with `red=True`, and (b) a new `conflict-probe` action when
`conflicting(pr.mergeable, pr.merge_state)`. Neither makes it a member, a merge candidate or a
stop. A member that is not the merge candidate this pass and reads conflicting also gets the
`conflict-probe`; the merge candidate keeps today's update path.

`_act` handles `conflict-probe`: it builds the repo's merge context (already built for the train),
runs a new `batch_merge.trial_conflicts(ctx, pr) -> list[str]` (the `_update` merge step plus
`_unresolvable`, aborted, scratch worktree removed), and when the refused list is non-empty raises
the same `MergeConflictError` into the existing `_conflict` path. An empty list is a no-op.

The board (`views.needs`) skips the `approve-pr` need for a PR whose batch has a `conflict` event
at the PR's head, and lists it as conflicting; failing PRs are already excluded (they are not
green) and keep the `failing-ci`/`red-pr` needs.

### E. The activity log (R22–R23)

`fr/triage/drive_log.py`: `DriveLog(state_dir)` with `append(kind, line, now)` (open-append-close
per line, so a crash never loses earlier lines; rotate to `drive.log.1` before a write that would
pass 5 MB), `tail(n)` and `follow()` (poll every second; on a size shrink or inode change reopen,
which follows a rotation). The driver's `_say` and its failure reports go through one
`_emit(kind, line)` that prints AND appends when a log is attached (loop mode with `--yes` only;
plan mode and `--once` attach none, so their output is unchanged). The supervisor appends its own
`restart`/`stop` lines to the same file. The board renderer reads `tail(50)` into an Activity
panel (the existing `components.py` tokens; long lines wrap at phone width). The file is
operator-facing only: nothing reads it to decide anything, and it is not carried by the state ref.

### F. Small fixes (R18–R20)

- `_fetched_reader`: `self._fetch_failed: dict[str, Exception]`; on a recorded failure raise it
  again; on a new failure record it and raise `TransientPassFailure("git:fetch", …)`.
- `swap_issue_labels`: docstring only, plus a unit test whose fake `_run_gh` applies the add and
  then refuses the removal.
- `batch cancel`: `dispatched = any(e.kind == "dispatch" for e in batch.events)`; `withdraws` is
  empty and the tracking gate is skipped when not dispatched; claim release (`execute(env, …)`)
  runs as before.

## Verification

strategy: none
gate: developer

- drive-pass-boundary: none — CI tests drive `_host_loop` with a fake remote refusing one push and a pass raising each failure class; the AST tripwire pins the boundary
- drive-failure-ledger: none — CI tests over the ledger writer, the board need and `drive failures --file` against a fake GhClient
- drive-session-supervisor: none — CI integration tests run a real supervisor and child process, SIGKILL the child and kill the parent
- drive-red-drafts: none — CI unit tests on both walks and `_recover` with fake sessions (idle, working, done)
- drive-conflict-early: none — CI tests with a fake forge reporting CONFLICTING and a scratch git repo for the trial merge
- drive-fetch-once: none — CI unit test counting fetches on a fake checkout that fails
- swap-labels-retry-converges: none — CI unit test with a fake `_run_gh` that applies part of a call, then refuses
- cancel-undispatched-no-checkout: none — CI CLI test of `batch cancel --yes` with no `--checkout` on a never-dispatched batch
- drive-activity-log: none — CI tests on `DriveLog` (append, rotate, follow across a rotation) and the board panel render

Every requirement is proven by unit and integration tests in CI with fakes: a fake remote that
refuses one state-ref push, fake runner sessions with idle/working/done statuses, a fake forge
reporting `CONFLICTING`, a scratch git repo for the trial merge, and a real child process the
supervisor tests kill with SIGKILL and orphan. The first resident-orchestrator drive is its own
future work.

## Out of scope

- The resident orchestrator agent itself (what it does on a wake).
- #1216 (one scope-owned writer for drive and page refresh): `StateRefConflict` stays a refusal.
- launchd/systemd units: the supervisor is session-bound by design.
