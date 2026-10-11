# Drive loop resilience — no silent single pass, retry unreadable visibility, REST free-plan 403

Batch `driver-resilience`: super-fr#1127, super-fr#1134, super-fr#1135. All three stopped or
stalled one org scope's wave-1 driver on 2026-10-10.

## Background

**#1127.** `fr triage batch drive --once --yes` reads like "start the waves", but it is one pass
that leaves no driver behind. It dispatches, prints `dispatched to herdr as …`, exits 0, and
then nothing merges ready PRs, closes out merged batches, dispatches held batches once their wave
or `--after` clears, or re-renders `board.html` (written only at the end of a `--yes` pass,
`_Driver._write_board`). An agent reused its dry-run command with `--yes` added and reported
success, and the board froze.

The issue asks for a guard on "no looping driver holds the lock at exit". The code makes that
condition redundant: `batch_drive_command` takes `drive_lock` (`triage_batch_cmd.drive_lock`)
for `--once` too, and with `--yes` the state-ref lease (`_Driver.take_lease`), and both refuse a
second driver. A `--once --yes` pass that reaches its plan is therefore already the scope's only
driver on this host and lease. A looping driver on another host of a scope with no state repo
can't be seen at all. So the guard reduces to "this `--once --yes` pass would dispatch".

**#1134.** A looping driver (`_host_loop`) exited on
`cannot read the visibility of the state repo …` (`privacy.unreadable`). The path is
`take_lease` / `save_pass` → `triage_cmd.push_now` → `state_ref.push_state` →
`privacy.guard_state`. That raises `PrivacyError` when `live_visibility` answers None, which it
does for every failure: rate limit, timeout, 5xx, unsupported backend. `take_lease` and
`save_pass` turn any `TriageError` into `_fail` (exit 2), which ends the loop. Other forge reads
in the pass raise `ForgeReadError`, which the loop already skips and retries after `--interval`
(gh#910). Skipping a save is safe: `state_ref.fetch_state` keeps local changes when the remote
ref has not moved, so the next pass pushes what the skipped one held.

**#1135.** Under `forge.api: rest`, `RealGhRestClient.required_check_names`
(`fr/real_ghrestclient.py:731`) reads `repos/{repo}/rules/branches/{b}` unconditionally. On
GitHub's free plan, a private repo answers that route with HTTP 403 and the message
`Upgrade to GitHub Pro or make this repository public to enable this feature.` That failure
skips every drive pass. It is the only reader of that route.

## Requirements

R1. `fr triage batch drive --once --yes`, when the pass's plan holds at least one `dispatch` action, refuses with exit 2 before acting on any action, unless `--single-pass` is given.
R2. That refusal releases the drive lease the pass took, and writes nothing else beyond what planning already writes (collected facts).
R3. The refusal message names what a single pass leaves undone: ready PRs merged, merged batches closed out, held batches dispatched when their wave or `--after` clears, the board refreshed. It also prints the looping command: `fr triage batch drive`, the caller's batch ids, the scope arguments (`triage_kanban_cmd.scope_args`), every non-default `--max-inflight`, `--interval`, `--workspace-prefix`, `--keep-sessions`, each `--checkout REPO=PATH` with PATH absolute (a single-repo scope's defaulted checkout, the working directory's toplevel, is printed explicitly as `--checkout OWNER/REPO=<abs toplevel>` so the command drives the same clone from any pane), and `--yes`, without `--once`.
R4. With `--single-pass`, a `--once --yes` pass whose plan holds a dispatch (the same condition as R1, whether or not the dispatch then starts) acts as today, then ends with a warning carrying R3's text and command; its exit code is `pass_exit`'s, unchanged.
R5. Unchanged: `--once` without `--yes` (the dry-run plan); a `--once --yes` pass whose plan holds no dispatch; loop mode; the cloud pass `fr triage drive pass`.
R6. `--single-pass` without `--once` is refused (exit 2), naming that it only applies to `--once`.
R7. The fr-triage skill states that starting or dispatching waves means the looping driver, and that `--once --yes` is a deliberate single pass that must say `--single-pass` when it dispatches.
R8. In loop mode, a state-repo visibility that cannot be read when the drive takes its lease or saves its pass, for any cause, skips the rest of that pass. Nothing more is written or pushed, it is reported once per distinct cause, and the drive reads again after `--interval`. The next pass whose read succeeds proceeds and pushes the state the skipped pass left. When a newer fr was installed by a `post_merge` (`restart_to` set), any skipped pass (this one, or a gh#910 forge-read skip) restarts on it instead of sleeping, as an unskipped pass would.
R9. `--once --yes`, the cloud pass and `fr triage state export` keep refusing (exit 2) on an unreadable state-repo visibility. (Plan mode takes no lease and pushes nothing, so it never reads that visibility.)
R10. A readable public state repo with a private member's key is refused in every mode, as today, and ends a looping driver as today.
R11. The state repo's visibility is read live before every push, as cloud-triage R8 requires; no answer is cached.
R12. The REST client's `required_check_names` treats a 403 from `rules/branches/{b}` whose message carries GitHub's plan-upgrade notice ("Upgrade to GitHub Pro or make this repository public") as "no rulesets": it returns the classic-protection contexts alone and reports nothing.
R13. Any other failure of that route, including any other 403, still raises as today.

## Design

### A. The single-pass guard (#1127: R1–R7)

`batch_drive_command` gains `--single-pass` (bool, default False). Validation happens before
`build_driver`: `--single-pass` without `--once` → `_fail` (R6).

The command builds the loop command once, as an argv list rendered with `shlex.join`. A pure
helper in `triage_batch_cmd` takes the command's own parameters, so it is unit-testable without a
driver. It also builds the shared message text: what a single pass leaves undone, then that
command (R3).

`build_driver` gains a keyword `single_pass: SinglePass | None = None`, where `SinglePass` is a
small frozen dataclass `(notice: str, allowed: bool)`; `_Driver` stores it as `single_pass` and
adds a memo `planned_dispatch: bool = False`. `batch_drive_command` passes it for `--once --yes`
only (`allowed` = `--single-pass`); the cloud pass (`triage_drive_cmd`, the only other
`build_driver` caller) never passes it, so R5 holds for the cloud pass by construction. In
`run_pass`, right after `plan = drive_pass(snap)` and before the action loop, when
`single_pass` is set the driver sets `planned_dispatch` iff the plan holds an action whose
`kind == "dispatch"` (`batch_drive.ActionKind`). Both R1 and R4 key on that one condition, the
plan, not on whether a dispatch then started (a held claim, a preflight refusal or a
`RunnerDispatchError` may stop it):

- the notice is set and `--single-pass` was not given → release the lease, then `_fail(notice,
  code=2)`. `batch_drive_command`'s `typer.Exit` handler keeps the lease on exit 2 ("a refusal
  keeps what it found"), so the release must happen before the raise (R2);
- `planned_dispatch` and `allowed` → act as today. `_host_loop`'s `once` branch prints the
  notice as a `warning:` line after the pass, before returning or raising its exit code (R4).

The loop command's checkout list comes from the same map the driver uses (`_checkout_map`), so a
single-repo scope's defaulted toplevel is printed as an explicit `--checkout` (R3).

Existing host tests that drive a dispatching `--once --yes` pass
(`tests/unit/test_triage_batch_drive_cmd.py`, `…_disruption.py`, `…_idle.py`, `…_restart.py`,
`test_triage_driver_pass.py` where it uses the host command) add `--single-pass`; that they then
pass unchanged otherwise is R4's "acts as today". Tests whose pass dispatches nothing are left
alone, which pins R5.

No action runs before the check, so a refused pass merges nothing either; the issue asks for the
refusal "before dispatching anything", and the plan is the first point where dispatch is known.

The fr-triage skill's driver paragraph (`plugins/super-fr/skills/fr-triage/SKILL.md`, the
`--once` sentence) states R7. The file is at the 120-line cap, so the text goes into that
existing line. The OpenCode and Hermes mirrors are regenerated with `scripts/sync-opencode.py`
and `scripts/sync-hermes.py`.

### B. Unreadable visibility skips the pass in loop mode (#1134: R8–R11)

`fr/triage/privacy.py` gains `class VisibilityUnreadable(PrivacyError)`. Every place that raises
`PrivacyError(unreadable(...))` raises it instead: `guard_state`, and `check_or_refuse`'s
unknown-state-repo branch. Existing `except PrivacyError` / `except TriageError` callers see no
change. The leak refusal (`refusal(...)`) stays a plain `PrivacyError` (R10).

`_Driver.take_lease` and `_Driver.save_pass` catch `VisibilityUnreadable` before their generic
`TriageError` → `_fail`, and raise `ForgeReadError(str(exc), code=2)`. `ForgeReadError` already
carries the policy:

- `_host_loop` in loop mode with `--yes` prints `warning: …; pass skipped, retrying every Ns` once
  per distinct message, sleeps `--interval` and runs the next pass (R8);
- `_host_loop` with `--once` calls `_fail(code=2)`, and so does the cloud
  pass (`triage_drive_cmd`, `except batch.ForgeReadError`) (R9).

`_host_loop`'s `ForgeReadError` branch, in loop mode, returns `driver.restart_to` when it is set
instead of sleeping (R8): a skipped `save_pass` comes after the pass, so its `post_merge` may
have installed a newer fr (gh#998), and the restarted process's first `take_lease` keeps the
unpushed local state (`fetch_state`) and pushes it.

A failed `take_lease` happens before the pass, so the whole pass is skipped. A failed `save_pass`
happens after the pass acted: the acts happened, but the state is not pushed. The next pass's
`fetch_now` keeps local changes while the remote ref has not moved (`fetch_state`), and its
`save_pass` pushes them. `fr triage state export` calls `guard_state` directly
(`triage_state_cmd`) and keeps exiting 2 (R9). Nothing is cached: `guard_state` reads live on
every call (R11).

### C. Free-plan rulesets 403 (#1135: R12, R13)

In `RealGhRestClient.required_check_names`, the `rules/branches/{b}` call is wrapped:
`except GhError as exc`, where a message containing `HTTP 403` and the plan-upgrade notice
`Upgrade to GitHub Pro or make this repository public` counts as no rules (an empty list). Any
other `GhError` re-raises (R13), and a `HostRefusedError` is never swallowed. The notice
substring is a module constant with a comment citing GitHub's message, so a reworded notice
fails one named test instead of being matched loosely. Nothing is reported (R12). The classic
`branches/{b}` read is unchanged. `RealGhClient` delegates to this method, so both backends get
the fix.

## Verification

strategy: none
- driver-once-dispatch-refused: none — unit tests drive `batch_drive_command` with fake runners and forge; the scenario needs no live forge to prove.
- driver-unreadable-visibility-retries: none — a rate-limited or failing visibility read cannot be produced on demand; a fake client raising is the proof.
- rest-rulesets-free-plan-403: none — the free-plan 403 needs a free-plan private repo; a fake `gh` run returning the captured message is the proof.

## Non-goals

- Caching visibility (R11; cloud-triage R8 stands).
- Classifying transient against permanent visibility failures: loop mode retries every unreadable answer, which still fails closed because nothing is written.
- Re-rendering `triage.html` from the driver (noted in #1127 as its own issue).
- Detecting a looping driver on another host of a scope with no state repo (invisible to this host).

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-10-11-driver-resilience | `derio-net/super-fr` | `2026-10-11-driver-resilience` | — |
