<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-batch-train-truth

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-19T10:51:15+00:00 input=true -->
### brief · discovery · Operator brief — batch train-truth (as dispatched)

/fr-goal batch train-truth

Batch `train-truth` of derio-net/super-fr: 6 issues, delivered as ONE pull request.
Members: #1491 (a transient refused state-ref push ends the drive loop, and nothing restarts the driver),
#1492 (red CI on an unapproved draft batch PR is never handed back), #1493 (merge conflicts are found only
when a PR heads the train, after it was approved), #1540 (_fetched_reader lets GitError escape and does not
record the failed fetch), #1541 (the swap_issue_labels retry assumes gh resolves all labels before mutating),
#1543 (batch cancel of a never-dispatched batch still needs --checkout).
Why together: all in the driver loop (batch_drive.py, triage_batch_cmd.py); #1492 and #1493 share the draft
non-member filter.
Delivery rules: branch feat/batch-train-truth; a draft PR as soon as the spec is committed whose body closes
each member with its own `Closes derio-net/super-fr#<n>` line; no member issue as a phase tracking_issue;
never add the approved-fr label.
Mid-brainstorm operator ask: "btw, I would like to watch the driver's actions. Is there a way to make this
event log easily visible?"

<!-- fr:journal kind=decision scope=spec id=d-resident-orchestrator created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-resident-orchestrator · decision · The driver is owned by a resident orchestrator session

Operator (round 1 clarification): the Wave Driver will eventually be manned by a resident orchestrator agent,
like the gates. The driver runs beside a persistent agent session that is responsible for it; the agent must
always know the driver is running; the driver keeps itself alive (itself or via a supervisor) without
consuming tokens wherever it breaks down; if the agent session is killed, the driver and its supervisor go
with it.

<!-- fr:journal kind=decision scope=spec id=d-1491-shape created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-1491-shape · decision · #1491: a session-bound supervisor (drive --supervise), not detached

Operator chose option 1 (round 1 Q1). The supervisor restarts the driver after a crash with bounded backoff and a crash-loop limit, stays in its caller's session, and dies with it; the background-exit notice is the agent's one wake.

<!-- fr:journal kind=decision scope=spec id=d-red-delivered created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-red-delivered · decision · #1492/#1493: the existing session-status rule decides when a draft is handed back

Operator chose the recommended option (round 1 Q2). Only an idle session is handed a red or conflicting draft; a working one is waited on; absent/done is a Needs you now entry. Caps count draft and ready hand-backs together.

<!-- fr:journal kind=decision scope=spec id=d-1541 created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-1541 · decision · #1541: make the retry assumption-free (docstring + unit test), no live walk

Operator chose the recommended option (round 1 Q3).

<!-- fr:journal kind=decision scope=spec id=d-1543 created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-1543 · decision · #1543: a never-dispatched cancel has no tracking gate and still releases claims

Operator chose the recommended option (round 1 Q4).

<!-- fr:journal kind=decision scope=spec id=d-verify created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-verify · decision · Verification: CI tests with fakes, strategy none, gate developer, no Test Plan

Operator chose the recommended option (round 1 Q5).

<!-- fr:journal kind=decision scope=spec id=d-root-fix created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-root-fix · decision · Fix the crash class at its root with a typed pass boundary

Operator chose the recommended option (round 2 Q1). Inside a pass, failures are a DriverRefusal (operator must act) or transient (reported once, capped exponential backoff, next pass re-reads); 10 failed passes in a row stop as a refusal; a tripwire forbids _fail/typer.Exit in the pass.

<!-- fr:journal kind=decision scope=spec id=d-refusal-loop created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-refusal-loop · decision · On a refusal the driver exits (the agent wakes), tied to a self-improvement loop

Operator (round 2 Q2): "1. but only if this is tied to a self-improvement loop, in order to driver the real
refusals to zero". Interpreted as R8-R9: every refusal, transient failure and crash is counted per stable
cause in a durable ledger, and `fr triage batch drive failures --file --yes` turns each recurring cause into
a tracked forge issue (commented as it recurs, re-filed if it recurs after closing), named by every refusal's
exit line and board need. Interpretation recorded for the operator to correct at PR review.

<!-- fr:journal kind=decision scope=spec id=d-activity-log created=2026-11-19T10:51:15+00:00 decided_by=operator -->
### d-activity-log · decision · The driver's actions are visible as a persistent activity log (drive.log, drive log -f, board Activity panel)

Operator's mid-brainstorm ask ("I would like to watch the driver's actions"), folded in as R22-R23 before the brainstorm resolved; the operator may veto it at PR review.

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-19T10:51:15+00:00 lens=errors step=brainstorm -->
### lens-errors-1 · lens · The pass boundary reclassifies every failure path of the driver; each must land in the right class

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-19T10:51:15+00:00 lens=tests step=brainstorm -->
### lens-tests-1 · lens · Process-lifetime and backoff behaviour is easy to test vacuously (sleeps, signals, orphaned children)

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-11-19T10:51:17+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: operator-request. the operator's round-1 answer on #1491 asked a question back (why does the driver keep crashing, is there a design defect); answering it from the code (31 _fail sites inside the pass, one ForgeReadError boundary) needed the root-fix and refusal-handling decisions

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · `drive status|failures|log` cannot be subcommands: `fr triage batch drive` is a command with variadic batch ids

triage_batch_cmd.py:7311-7316 (`drive` leaf command, positional `batch_ids`); loop command argv :3337; gh#998 re-exec :7425. Put the verbs on the existing `fr triage drive` group (triage_drive_cmd.py:64-69) and name that shape in R9, R13, R22 and §B, §C, §E.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · R6's tripwire forbids what §A puts in `_host_loop`, and what `_host_loop` already does

`_host_loop` has `_fail` :7262, `raise typer.Exit` :7294 (--once) and :7304 (stalled). Say how --once, plan mode and a stall leave the loop (a typed result that `batch_drive_command` converts), or narrow the tripwire.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · The boundary misclassifies refusals raised by module-level helpers the pass calls; typer.Exit is not SystemExit

`_act` calls `dispatch_batch` (:5555, defined :1817), which `_fail`s for the tracking gate (:1857) and runner refusals (:1970-:1975). `typer.Exit` is click's `Exit(RuntimeError)` (triage_kanban_cmd.py:93-95), so `except Exception` would retry it as transient. Classify it explicitly.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · Lease renewals during budget waits are outside the boundary

Only `one_pass` is in the `try` (:7258-7276); `before_pass`/`wait_out` (:7249-7252, :7268, :7284, :7306) call `take_lease` (:3527), which `_fail`s (:3998-3999). After §A that is an uncaught exception with no ledger entry. Cover the waits.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · The cloud entry `fr triage drive pass` catches only ForgeReadError, so the new exceptions escape it

triage_drive_cmd.py:581-600. Give `drive_pass_command` its own mapping (refusal 2, transient today's code, outbox still written) and a test.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · R5 says today's exit codes stay, but the new exceptions carry no code

Codes come from each `_fail(..., code=)` site, e.g. code=1 for a failed dispatch (:6307). Carry a `code` on the exceptions.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · LeaseHeld and LeaseExpired are missing from R2's refusal list, so they become transient

lease.py:77-90, :166-177 (`LeaseExpired` needs `fr triage lease take --yes`); `take_lease` `_fail` :3998-3999. Add both to R2 with cause ids and resume commands.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · The R7 stopped-driver need cannot show: a refusing driver keeps its lease, and no pass renders the board after it

Code 2 keeps the lease (:7411-7413), live up to ~75 min (lease.py:105-110). Treat a refusal newer than the lease's last pass as stopped, and render the board once before exit 2.

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · "Carried by the state ref" needs a REF_FILES change, and the ref's contract excludes host-local identity

state_ref.py:53-69 (`REF_FILES`), :7-8 (host-only files never ride). `driver.yaml` holds a pid and host id; a shared ledger adds a CAS conflict surface. Decide what rides and say so.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · Reusing `_conflict` for a draft starts a fresh conflict session, against d-red-delivered and R16's "idle sessions only"

`_hand_back` falls through to `_fresh_conflict` for absent/done (:6224-6229); `_conflict` records a merge stop (:5953); the error text says the worktree is kept (batch_merge.py:640-642). Give the probe its own delivery (idle hand-back, working wait, absent/done to Needs you), say whether it writes merge-stops.json, fix the worktree text.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · Trial merges repeat every pass with no memo, and draft-only repos add forge reads beyond the one `pr_view`

A DIRTY PR whose conflicts are all resolvable records no event (batch_drive.py:877-878) and is trial-merged every pass. Memoise per (PR, head, base sha); the merge context build reads merge methods/rules (:4087-4107, :4120-4124) — avoid or allow those reads.

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · R18's design raises a non-TriageError, which skips every caller's existing degradation

`GitError(TriageError)` (gitseam.py:35); callers degrade on TriageError (`_ci_none` :4842-4847, :4491, :4545, :4693, :4862, :4875). Re-raise the recorded `GitError`.

<!-- fr:journal kind=finding scope=spec id=sr-13 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-13 · finding [open] (reviewer: in scope) · R15's train line cannot list stepped-over drafts: the walks return no Train when there are no members

batch_drive.py:1537-1538, :1672-1673; `stepped` only for members (:1556, :1642). Put non-member red PRs in `stepped` and build a Train when only non-members exist, or drop the clause.

<!-- fr:journal kind=finding scope=spec id=sr-14 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-14 · finding [open] (reviewer: in scope) · The supervisor is underspecified: argv, lock and lease, a child stopped by signal, and the crash-loop exit code

Child argv must be the interpreter (`fr_argv`, safe_spawn.py:18-20) less `--supervise`; the supervisor must not take `drive.lock` (:3585-3592) or the lease; a signal to the child is a clean stop today (`_sigterm_interrupts` :7215-7234, :7405-7407) and must not be restarted; R12 needs a crash-loop exit code.

<!-- fr:journal kind=finding scope=spec id=sr-15 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-15 · finding [open] (reviewer: in scope) · R9 does not say which repo a driver-failure issue is filed in, or how private detail stays out of it

Org/group scopes span many repos; the last message carries repo names, heads and paths (privacy guard fr/triage/privacy.py). Name the target repo and whose settings gate it; keep the message out of the issue.

<!-- fr:journal kind=finding scope=spec id=sr-16 created=2026-11-19T11:04:37+00:00 state=open review_scope=in -->
### sr-16 · finding [open] (reviewer: in scope) · Stale or wrong names in the spec

`views.needs` is `needs_you` (views.py:277); a `merge-conflict` need exists (views.py:405-414); `conflicting()` is used elsewhere too (kanban.py:516, render.py:612, views.py:434); `_host_loop` is at :7237; `_sleep`/`wait_out` are module-level (:3465, :3516).

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-19T11:04:37+00:00 -->
### spec-review-1 · review · independent spec review: 16 findings, all in scope, all fixed in the spec

Reviewer fr-spec-reviewer raised sr-1..sr-16, every one tagged in scope. All are fixed in the
rewritten spec (requirements renumbered R1-R24; the pending rows' origins corrected with
`fr acceptance amend --origin`). Decisions honoured; d-red-delivered now honoured for conflicting
drafts too (R17: absent/done is a held conflict, never a fresh session). The reviewer's suggested
`simplicity` lens is added.

<!-- fr:journal kind=lens scope=spec id=lens-simplicity-1 created=2026-11-19T11:04:37+00:00 lens=simplicity step=spec-review -->
### lens-simplicity-1 · lens · One PR adds a pass boundary, a supervisor, a ledger with issue filing, an activity log and three verbs; each must earn its place

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: `drive status|failures|log` cannot be subcommands: `fr triage batch drive` is a command with variadic batch ids

Verbs moved to the existing `fr triage drive` group: `fr triage drive status|failures|log` (R10, R14, R22, §B, §C, §E).

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: R6's tripwire forbids what §A puts in `_host_loop`, and what `_host_loop` already does

R7: deliberate ends leave `_host_loop` as a returned `LoopEnd` that `batch_drive_command` converts; the tripwire covers `_Driver`, `one_pass`, `_host_loop`, `wait_out` (§A).

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: The boundary misclassifies refusals raised by module-level helpers the pass calls; typer.Exit is not SystemExit

R4: a click `Exit` reaching the boundary is classified by code (2 refusal with cause `exit:<function>`, else transient); a behavioural test covers `dispatch_batch` (§A).

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: Lease renewals during budget waits are outside the boundary

R1 and §A: one `try` wraps the whole iteration, pacing waits and renewals included.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: The cloud entry `fr triage drive pass` catches only ForgeReadError, so the new exceptions escape it

R6 and §A: `drive_pass_command` classifies the same way, writes its outbox and exits with the carried code.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: R5 says today's exit codes stay, but the new exceptions carry no code

R2/R3: both exception types carry `code` (refusal 2; transient 2, or 1 where the site used code=1).

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: LeaseHeld and LeaseExpired are missing from R2's refusal list, so they become transient

R2 lists `LeaseHeld` and `LeaseExpired` (resume `fr triage lease take --yes`).

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: The R7 stopped-driver need cannot show: a refusing driver keeps its lease, and no pass renders the board after it

R8: the board renders once before exit 2 and the need shows while the recorded refusal is newer than the lease's last pass; the lease rule is unchanged.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: "Carried by the state ref" needs a REF_FILES change, and the ref's contract excludes host-local identity

R9 and §B: both files are host-local, not in `REF_FILES`; the state_ref docstring names them.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: Reusing `_conflict` for a draft starts a fresh conflict session, against d-red-delivered and R16's "idle sessions only"

R17 and §D: the probe's own delivery (idle hand-back via the message path only, working/unknown wait, absent/done a `held` conflict event), no merge stop, no 'worktree kept' text (scratch always removed).

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: Trial merges repeat every pass with no memo, and draft-only repos add forge reads beyond the one `pr_view`

R17 and §D: memo per (PR, head, base sha) per process; `trial_conflicts` needs only the fetched clone and version config, so no merge-methods or rules read.

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: R18's design raises a non-TriageError, which skips every caller's existing degradation

R19 and §F: the recorded `GitError` is re-raised, so each caller's handler decides.

<!-- fr:journal kind=finding scope=spec id=sr-13-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-13 -->
### sr-13-resolved · finding [fixed] · resolves sr-13: R15's train line cannot list stepped-over drafts: the walks return no Train when there are no members

R16 and §D: red non-members go into `stepped`; a Train is returned when the repo has a member or a red or conflicting non-member.

<!-- fr:journal kind=finding scope=spec id=sr-14-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-14 -->
### sr-14-resolved · finding [fixed] · resolves sr-14: The supervisor is underspecified: argv, lock and lease, a child stopped by signal, and the crash-loop exit code

R11/R13 and §C: child via `fr_argv` less `--supervise`; supervisor takes no lock or lease; the child's own clean stop on SIGINT/SIGTERM/SIGHUP is deliberate; crash-loop exits 2.

<!-- fr:journal kind=finding scope=spec id=sr-15-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-15 -->
### sr-15-resolved · finding [fixed] · resolves sr-15: R9 does not say which repo a driver-failure issue is filed in, or how private detail stays out of it

R10: target is the scope's state repo, else the single-repo scope's repo, refused otherwise; that repo's settings gate it; the issue never carries the message text.

<!-- fr:journal kind=finding scope=spec id=sr-16-resolved created=2026-11-19T11:04:37+00:00 state=fixed resolves=sr-16 -->
### sr-16-resolved · finding [fixed] · resolves sr-16: Stale or wrong names in the spec

Names corrected (`needs_you`, `_host_loop` :7237, module-level `_sleep`/`wait_out`, `conflicting()` scoped to batch_drive.py); R18 reuses the existing `merge-conflict` need for held conflicts so one PR has one row.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-19T11:04:41+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  cancel-undispatched-no-checkout: none
  drive-activity-log: none
  drive-conflict-early: none
  drive-failure-ledger: none
  drive-fetch-once: none
  drive-pass-boundary: none
  drive-red-drafts: none
  drive-session-supervisor: none
  swap-labels-retry-converges: none
row_kinds:
  cancel-undispatched-no-checkout: none
  drive-activity-log: none
  drive-conflict-early: none
  drive-failure-ledger: none
  drive-fetch-once: none
  drive-pass-boundary: none
  drive-red-drafts: none
  drive-session-supervisor: none
  swap-labels-retry-converges: none
run_gate: developer
run_kind: none
```

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-19-batch-train-truth-p1 created=2026-11-19T11:08:21+00:00 -->
### tier-2026-11-19-batch-train-truth-p1 · decision · hard: phase 1 rewrites the error path every driver caller (host loop, cloud pass, --once) relies on

Reclassifies ~30 _fail sites and the loop boundary; a misclassification either kills the loop or retries a refusal.
