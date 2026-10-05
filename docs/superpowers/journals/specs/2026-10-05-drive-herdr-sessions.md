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
