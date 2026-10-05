# Journal: 2026-10-05-drive-herdr-sessions

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-05T11:52:10+00:00 input=true -->
### operator-brief · discovery · Batch drive-close-tabs brief (super-fr#918, super-fr#919)

/fr-goal Drive manages its herdr sessions: one workspace per wave, finished sessions closed

Batch `drive-close-tabs` of derio-net/super-fr: 2 issues, delivered as ONE pull request.

## super-fr#918: Drive leaves a finished batch's runner sessions open (batch and close-out tabs)
drive leaves a finished batch's batch and close-out runner sessions open

## super-fr#919: Drive: open each wave's sessions in a herdr workspace of its own (<prefix>-wave-<n>)
drive should open each wave's sessions in a herdr workspace of its own

## Why these belong together
#918 and #919 are the same runner-protocol extension (a wave/group hint and a close operation on the work item); one design covers both. Shares the close-out/archive path with drive-closeout-recognition.

## Delivery rules
- Work on branch `feat/batch-drive-close-tabs`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#918
  Closes derio-net/super-fr#919
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=discovery scope=spec id=herdr-sees-status created=2026-10-05T11:52:10+00:00 -->
### herdr-sees-status · discovery · herdr reports per-tab agent status and lists tabs across workspaces

`herdr tab list` carries `agent_status` (idle|working|blocked|done|unknown, AgentStatus
enum, protocol 22); without `--workspace` it lists every workspace's tabs.
`workspace create` returns workspace, first tab and root pane. The wave-driver premise
"the runner cannot see whether a session ended" no longer holds.

<!-- fr:journal kind=discovery scope=spec id=isolation-host-worktree created=2026-10-05T11:52:10+00:00 -->
### isolation-host-worktree · discovery · Run isolated in host-worktree mode

Docker (colima) was unreachable at start, so the devcontainer up failed; the run was started with FR_ISOLATION_TARGET=worktree, as other recent runs on this repo were.

<!-- fr:journal kind=decision scope=spec id=q1-default-prefix created=2026-10-05T11:52:10+00:00 -->
### q1-default-prefix · decision · Default prefix is `drive` (drive-wave-<n>, drive-no-wave)

Operator chose the fixed neutral default over a scope-derived one or opt-in grouping.

<!-- fr:journal kind=decision scope=spec id=q2-closable-status created=2026-10-05T11:52:10+00:00 -->
### q2-closable-status · decision · Close idle, done and unknown; skip working and blocked

Operator chose: all but working/blocked are closable; busy ones retried next pass.

<!-- fr:journal kind=decision scope=spec id=q3-close-default created=2026-10-05T11:52:10+00:00 -->
### q3-close-default · decision · Closing is on by default; --keep-sessions opts out

Operator chose default-on with an opt-out flag.

<!-- fr:journal kind=decision scope=spec id=q4-empty-workspace created=2026-10-05T11:52:10+00:00 -->
### q4-empty-workspace · decision · An emptied wave workspace is closed; the driver's own never

Operator chose to close a workspace whose last tab the driver closes.

<!-- fr:journal kind=decision scope=spec id=q5-batch-tab-timing created=2026-10-05T11:52:10+00:00 -->
### q5-batch-tab-timing · decision · Batch tab closes with the close-out tab, at archive merge

Operator chose the #918 trigger for both tabs over closing the batch tab at its PR merge.

<!-- fr:journal kind=decision scope=spec id=q6-test-plan created=2026-10-05T11:52:10+00:00 -->
### q6-test-plan · decision · Post-merge Test Plan: a live two-wave drive

Operator chose a live two-wave drive inside herdr as the owed post-merge run.

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-10-05T11:56:56+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · Busy sessions are never retried once the drive is done: loop exits on summary.done

R8/Test Plan promised a later-pass retry, but R10 means the last pass reports done and the loop returns (triage_batch_cmd.py:2052-2059); close's `did` was unspecified, so --once's exit code could change.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-10-05T11:56:56+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · Close probe's runner unspecified; loading one can exit 2, breaking R10

`_Driver.runner` -> `load_runner` calls `_fail` (triage_batch_cmd.py:173-187); vk/cncd cannot be built outside their bridge (registry.py:77); `hand` close-outs have no runner; current `_launch` may differ from where the session went.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-10-05T11:56:56+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · R9 closes any single-tab workspace other than the runner's own; q4 covers only wave workspaces

A tab moved by hand into an operator workspace, alone there, would close that workspace.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-10-05T11:56:56+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · `herdr tab rename` relied on but not among the verified herdr facts

Background listed tab list/workspace create/close/tab close only; the first dispatch into a new wave depends on the rename.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-10-05T11:56:56+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · Test Plan covers only the live happy path; R2, R4, R6, R9, R10 untested

The deterministic parts (pure drive_pass, faked _run_herdr) have no automated verification listed.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-10-05T11:56:56+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · fr-triage skill's driver paragraph not updated for the new flags and closing

plugins/super-fr/skills/fr-triage/SKILL.md:96 documents drive's flags and per-pass behaviour.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-10-05T11:56:56+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · R3 'same group as the batch' false for a hand-dispatched or re-waved batch

The close-out gets wave_group(prefix, wave) while the batch tab may sit in the runner's own workspace.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-10-05T11:56:56+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · R1 'reused by every later one' conflicts with R9 closing an emptied wave workspace

A later dispatch into a closed wave workspace recreates it.

<!-- fr:journal kind=review scope=spec id=spec-review-r1 created=2026-10-05T11:56:56+00:00 -->
### spec-review-r1 · review · independent spec review: 8 findings

Reviewer (fr-spec-reviewer, dispatched by this session) raised sr-1..sr-8, all in scope.
Decisions q1, q2, q3, q5, q6 honoured; q4 widened (sr-3). Verified the named files and
helpers with file:line (runner.py, protocols.py, work_item.py, testing.py, registry.py,
batch_drive.py, triage_batch_cmd.py, model.py, wave-driver spec).

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-10-05T11:56:56+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: Busy sessions are never retried once the drive is done: loop exits on summary.done

Chose to state the limit: R8 now says a done drive does not wait for a busy session and a later drive closes it; R10 and §D say close returns did=False and never changes the exit code; Test Plan 2 reworded.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-10-05T11:56:56+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: Close probe's runner unspecified; loading one can exit 2, breaking R10

§D: probe the runner each event recorded (DispatchEvent for the batch item, CloseoutEvent for the close-out), skip `hand`, one preflight/existing call per runner, via a non-exiting load; a load failure, non-closer or preflight refusal skips that runner (reported once where it is not just a non-closer). R10 names the load failure.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-10-05T11:56:56+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: R9 closes any single-tab workspace other than the runner's own; q4 covers only wave workspaces

R9 and §B: the lone tab's workspace closes only when its label equals the item's payload group and it is not the runner's own; otherwise only the tab closes. Probe items carry the group.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-10-05T11:56:56+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: `herdr tab rename` relied on but not among the verified herdr facts

Verified live: `herdr tab rename <TAB_ID> <LABEL>...`; recorded in Background, and §B says a failed rename is a failed dispatch that closes the workspace.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-10-05T11:56:56+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: Test Plan covers only the live happy path; R2, R4, R6, R9, R10 untested

Added an `Automated verification (CI)` section listing unit-level checks for every requirement the live Test Plan does not cover.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-10-05T11:56:56+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: fr-triage skill's driver paragraph not updated for the new flags and closing

Added §E: update fr-triage SKILL.md's driver paragraph and regenerate the OpenCode and Hermes mirrors.

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-10-05T11:56:56+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: R3 'same group as the batch' false for a hand-dispatched or re-waved batch

R3 reworded to the built rule: the close-out opens in the group of the batch's CURRENT wave, wherever the batch's session is.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-10-05T11:56:56+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: R1 'reused by every later one' conflicts with R9 closing an emptied wave workspace

R1 reworded: created when no workspace carries the label, reused while one does, recreated after R9 closes it.
