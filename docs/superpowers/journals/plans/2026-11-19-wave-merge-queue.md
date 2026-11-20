<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-wave-merge-queue

<!-- fr:journal kind=decision scope=plan id=plan-shape created=2026-11-19T22:30:03+00:00 -->
### plan-shape · decision · Seven agentic phases, one per reviewable ask, no manual phase

State model and approval (skeleton), pure planner, executor, hold handshake, one merge path, gates and close-out, operator view. No manual phase - the live proof is the post-merge row wave-queue-live-wave; super-fr's main ruleset forbids only force-push and deletion, so R34's direct push needs no operator setup today.

<!-- fr:journal kind=decision scope=plan id=p1-patch-id-unreadable-falls-back created=2026-11-20T02:39:16+00:00 phase=1 -->
### p1-patch-id-unreadable-falls-back · decision · An unreadable live patch-id is judged by reaches(), never as Void or Approved (phase 1)

`approval_verdict(..., patch_id=None)` with a recorded patch-id falls back to today's
`reaches()` rule, exactly as for an approval recorded before schema 13. The command
layer's `patch_id_reader` answers None when git cannot say (no branch known for the
PR, a head the clone cannot reach after one fetch of the PR branch, no default
branch), so a missing clone or a fake one degrades to the old rule rather than voiding
every approval or approving on no evidence. The reader is built once per repo per
pass over the clone fetched once per pass (the per-pass reset moved before the
settle, so the settle's reads share the pass's one fetch).

<!-- fr:journal kind=decision scope=plan id=p1-fr-updates-keep-approval created=2026-11-20T02:39:16+00:00 phase=1 -->
### p1-fr-updates-keep-approval · decision · Until R22 removes PR-branch updates, reaches() over fr's own updates also keeps an approval (phase 1)

The first closing suite failed four real-git integration tests
(test_triage_batch_merge_git.py): the legacy merge train re-slots a PR's version by
updating its branch, which changes its diff and so its patch-id, and the second PR
read Void. Spec §E reads "Void when it differs"; the verdict now is Approved when the
patch-ids are equal OR fr's recorded updates lead from the approved head to the live
one (the approved head itself included), Void otherwise. Each half is sound on its
own: equal content, or a push fr made. A foreign push that changes the diff still
voids. Phase 5 (one merge path, R22) stops fr updating PR branches; revisit there
whether the reaches() half should narrow to approvals with no patch-id.

<!-- fr:journal kind=decision scope=plan id=p1-merge-gate-reads-patch-id created=2026-11-20T02:39:16+00:00 phase=1 -->
### p1-merge-gate-reads-patch-id · decision · The merge gate (batch_merge._approved_and_ready) and `batch merge` read the patch-id too (phase 1)

The plan named `_settle_approvals` and the snapshot's verdict. The merge-time gate in
`batch_merge._approved_and_ready` re-judges the approval, and without the patch-id it
would have refused (Void by reaches) a PR the snapshot had just judged Approved after a
merge of main. So `MergeContext` gained an optional `patch_id_of`, set each pass by the
driver and by `fr triage batch merge`, which also settles with it. "A PR is approved
the same way everywhere" (approval.py) stays true.

<!-- fr:journal kind=discovery scope=plan id=p1-patch-id-in-schema-13 created=2026-11-20T02:39:16+00:00 phase=1 -->
### p1-patch-id-in-schema-13 · discovery · ApprovalEvent.patch_id landed with the schema-13 model (T2), not in T3.S4 (phase 1)

Spec §E says judgements schema 13 adds `ApprovalEvent.patch_id`, so it was added in the
schema bump, with a refusal of a patch-id in a file stamped below 13. T3.S4's threading
(verdict, settle, command layer) is as planned.

<!-- fr:journal kind=discovery scope=plan id=p1-test-fakes-gain-patch-id created=2026-11-20T02:39:16+00:00 phase=1 -->
### p1-test-fakes-gain-patch-id · discovery · The merge and drive test fakes now answer reach_commit/patch_id (phase 1)

`FakeCheckout` (test_triage_batch_merge.py) and `DriveCheckout`
(test_triage_batch_drive_cmd.py) raise GitError from `patch_id`, so their approval
tests keep judging by reaches(). Schema pins (12 -> 13) were moved in 13 test files,
the fr-triage skill (and both mirrors), AGENTS.md, docs/herdr-control-sessions.md and
the two triage explainers.

<!-- fr:journal kind=discovery scope=plan id=p1-host-load created=2026-11-20T02:39:16+00:00 phase=1 -->
### p1-host-load · discovery · The host ran at load 30-45 on 12 cores during this phase (phase 1)

P1.T1.S1's "run the full suite and confirm green" was started and stopped at 2% after
five minutes (shared-host load). A full run took 2 h at six workers; its one unrelated
failure (test_suite_isolation_inherited_columns, a subprocess timeout under load)
passed alone. The closing suite is the log named in evidence.

<!-- fr:journal kind=lens scope=plan id=lens-security-1 created=2026-11-20T02:39:16+00:00 phase=1 lens=security step=implement-phase -->
### lens-security-1 · lens · The approval gate now trusts equal diff content (patch-id) instead of an fr-made head chain (phase 1)

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-20T02:39:16+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a smoke test and a change fragment; there is no code to clean

<!-- fr:journal kind=decision scope=plan id=p1-fr-updates-record-patch-id created=2026-11-20T03:11:58+00:00 phase=1 decided_by=agent -->
### p1-fr-updates-record-patch-id · decision · fr's own updates record their new head's patch-id; an approval holds at any id fr recorded since it (supersedes p1-fr-updates-keep-approval's reaches-only carry-over) (phase 1)

Review finding p1-r7: under p1-fr-updates-keep-approval an fr update was carried only by reaches(), so a clean merge of main AFTER an fr update voided the approval (the recorded patch-id is the pre-update one, and reaches does not lead to the merge head). Now UpdateEvent gains an optional patch_id (schema 13, unreleased on this branch, so no migration; older events have none), _update records the patch-id of head_after before the push, and the verdict is Approved when the live patch-id equals any id recorded since the live approval (its own, or an fr update's after it), else reaches(), else Void. Every id in that set is approved content or fr's own update of approved content, so the set is no wider than what the operator approved. reaches() stays as the fallback for an unreadable id and for approvals with none; p1-r8 makes such an approval gain an id once it holds and the id reads.

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-11-20T06:45:38+00:00 phase=1 -->
### p1-review-1 · review · Phase 1 review — eight findings, all in scope, all fixed (phase 1)

An independent reviewer read the phase 1 diff (5f2f3ae23..924d3732d) against R12, R24 and §E.
It confirmed the schema 12→13 handling, the fail-closed fallback to reaches(), and that
the fr-update fallback cannot be forged by a foreign push. It raised eight in-scope
findings (p1-r1..p1-r8), fixed in 04e7629bf..cdd0d1746; the full suite after the fixes
passed (16922 passed, 122 skipped). The fix round also found and fixed one more defect:
pr_branches left out issue-linked PRs, so live reads silently fell back to reaches().

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-20T06:45:38+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · patch-id ignores hunk line numbers; moving an identical hunk keeps the approval while docs claim every diff change voids (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-20T06:45:38+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Checkout.patch_id ran porcelain git diff honouring textconv, external diff and host diff config (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-20T06:45:38+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · patch-id read against a stale origin/<default> voids a valid approval after a clean merge of newer main (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-20T06:45:38+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · no test ran the command-level wiring (driver settle, snapshot, merge gate) with a real patch-id (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-20T06:45:38+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · the model refusal of ApprovalEvent.patch_id below schema 13 had no test (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-20T06:45:38+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · the merge gate's void reason said "head moved" when the patch-id changed (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-11-20T06:45:38+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · a clean merge of main after an fr update voided the approval (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-11-20T06:45:38+00:00 phase=1 state=open review_scope=in -->
### p1-r8 · finding [open] (reviewer: in scope) · an approval first recorded without a patch-id stayed on reaches() for good (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-20T06:45:38+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: patch-id ignores hunk line numbers; moving an identical hunk keeps the approval while docs claim every diff change voids (phase 1)

Spec R12/§E and Test Plan item 5 state the limit; skill (both mirrors), explainers and AGENTS.md no longer overclaim; row reworded by amendment; limit pinned by tests/unit/test_gitseam_patch_id.py (moved identical hunk test).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-20T06:45:38+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Checkout.patch_id ran porcelain git diff honouring textconv, external diff and host diff config (phase 1)

PATCH_ID_DIFF pins --no-ext-diff --no-textconv --no-renames, myers, -U3, prefixes, -O/dev/null and -c config, GIT_DIFF_OPTS; R12 gives the command; tests for hostile config, textconv same-size binary edit and external diff in test_gitseam_patch_id.py.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-20T06:45:38+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: patch-id read against a stale origin/<default> voids a valid approval after a clean merge of newer main (phase 1)

judge_approval rereads with fresh=True on a mismatch, refetching the default branch once (Checkout.refresh_remote_branch); real-remote tests for stale main kept and a real change voided.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-20T06:45:38+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: no test ran the command-level wiring (driver settle, snapshot, merge gate) with a real patch-id (phase 1)

fakes return real ids; keep/void tests at batch merge (test_triage_batch_merge.py) and the driver (test_triage_batch_drive_cmd.py); each of the five call sites broken in turn fails a test.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-20T06:45:38+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: the model refusal of ApprovalEvent.patch_id below schema 13 had no test (phase 1)

test_triage_queue_model.py refuses approval and update patch_id below schema 13.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-20T06:45:38+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: the merge gate's void reason said "head moved" when the patch-id changed (phase 1)

shared void_reason in approval.py used by settle, dry run and _approved_and_ready; test_merge_train_gate.py.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-11-20T06:45:38+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: a clean merge of main after an fr update voided the approval (phase 1)

UpdateEvent.patch_id recorded by _update; the verdict approves any id fr recorded since the live approval; decision p1-fr-updates-record-patch-id; tests in test_triage_approval.py, test_merge_train_gate.py, test_triage_batch_drive_cmd.py.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-11-20T06:45:38+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: an approval first recorded without a patch-id stayed on reaches() for good (phase 1)

settle records a refreshing ApprovalEvent with the id once readable while the approval still holds; dry run says "would pin"; tests in test_triage_approval.py.

<!-- fr:journal kind=discovery scope=plan id=p2-suite-evidence-unbound created=2026-11-20T08:33:03+00:00 phase=2 -->
### p2-suite-evidence-unbound · discovery · Phase 2's full-suite log is not bound as step evidence (phase 2)

The executor's full suite passed (16959 passed, 122 skipped, exit 0, log wave-p2-suite.log).
The orchestrator had claimed the unit under a placeholder agent id, so the claim was abandoned
and re-opened after the run; fr binds a tests log only to a command of the current holder made
since the unit opened, so the log is left out. deliver's own full suite covers this phase.

<!-- fr:journal kind=decision scope=plan id=p2-queue-built-parent created=2026-11-20T08:33:03+00:00 phase=2 -->
### p2-queue-built-parent · decision · QueueBuiltEvent gains an optional `parent` (the commit the combination was built on) (phase 2)

The planner rebuilds each slot's chain (which entries a combination holds) from the
records alone (R24). `base` names the queue's main, not the combination ahead, so a
chain could not be recovered after a landing or a fresh rebuild. `parent` (None reads as
`base`) makes it exact and keys R13's "one rebuild per tree" as (parent, entry, head).
Schema 13 is unreleased on this branch, so no migration (as p1-fr-updates-record-patch-id).
Phase 3's executor must write it.

<!-- fr:journal kind=decision scope=plan id=p2-queue-only-for-configured-repos created=2026-11-20T08:33:03+00:00 phase=2 -->
### p2-queue-only-for-configured-repos · decision · plan_queue replaces _walk_train only for repos in Snapshot.wave_queues; others keep the train until phase 5 (phase 2)

`Snapshot.wave_queues` (repo -> QueueConfig) is empty until phase 3 builds it from the
`queue:` config block, so no repo changes behaviour yet and the board/`drive --plan`
are untouched. For a queue repo, drive_pass runs no train; the queue's report actions
become pass actions (queue-held -> held, queue-need -> blocked and counted, queue-warn
-> warn keyed in warned); the command prints the rest as `<kind> <repo>: ... : planned,
not executed` under --yes. Pass gains `queues`; wave_queue defines a minimal
`queue_line` that phase 7 replaces. QueueConfig is a dataclass in wave_queue for now.

<!-- fr:journal kind=decision scope=plan id=p2-reupdate-removed-with-executor created=2026-11-20T08:33:03+00:00 phase=2 -->
### p2-reupdate-removed-with-executor · decision · With red_decision's reupdate rule went the driver's _reupdate, batch_merge.update_failing and the red path's base fetch (phase 2)

red_decision is now (events, pr, head, failing, status). Its only executor and
update_failing/_open_head_unready became dead, so they were removed now rather than in
phase 5 (whose list names them). Tests: rule-2 tests in test_merge_train_red_decision
replaced by one hand-back test (rules renumbered), the cmd re-update tests replaced by
a moved-base hand-back test, and tests/scenarios/merge-train-red-recovery.sh phase A now
asserts an fr-made red head is handed back and never updated (scenario green).
Row merge-train-red-recovery amended (reword, drop/add the renamed level, set-status ci).

<!-- fr:journal kind=decision scope=plan id=p2-planner-shape created=2026-11-20T08:33:03+00:00 phase=2 -->
### p2-planner-shape · decision · How the planner reads the spec's open points (phase 2)

- queue-open is planned alone; builds start the pass after `queue_open` is recorded.
- A between-waves queue holds one entry: the one built, else the oldest ready; it
  drains once it landed something.
- Readiness order: the latest approval event, or a later eject in this record (a
  re-entered entry joins at the back).
- Build conflicts reach the planner as QueueSnapshot.conflicts (entry -> head, paths),
  which phase 3's executor fills; the eject carries conflict_decision's kind (skip
  included: the hand-back was already made).
- The red retry and the queue-build after a landing are planned in the same pass as the
  landing; the retried entry keeps its slot.
- R30's proposal never names a batch that is an active queue entry (it moves by
  building and landing); "no progress" needs both its last event (batch events and queue
  events naming it) and its last head change (unknown counts as old) past stall_hours.
- R36's cap exemption applies only while the repo's queue is open.
- The wave close-out is an input (QueueSnapshot.closeout_landed) until phase 6.

<!-- fr:journal kind=discovery scope=plan id=p2-acceptance-check-behind-main created=2026-11-20T08:33:03+00:00 phase=2 -->
### p2-acceptance-check-behind-main · discovery · fr acceptance check reports refs of rows merged on main whose tests are not on this branch (phase 2)

The branch is behind origin/main; the fold reads main's rows (git-answers-cached-per-invocation,
scenario-tier-deselected-locally, fast-tier-advisory-and-refused) whose tests and spec are
not here, so check prints ref errors unrelated to this run. A merge of main clears them.
The three phase-2 rows stay not-implemented with level refs: only the planner exists.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-20T08:33:03+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

a new module of small pure readers (effective_wave, is_terminal, queue_phase, _ready); nothing duplicated to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-20T08:33:03+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

replay/_valid/_plan_open were written once against the final combination model (parent-chained combos); no second copy of the slot logic exists to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-20T08:33:03+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

ejection reuses batch_drive.red_decision and conflict_decision unchanged in shape; the cleanup was the removal of the reupdate rule, its executor and update_failing in the same commit

<!-- fr:journal kind=decision scope=plan id=p2-queue-opens-on-first-ready created=2026-11-20T08:42:29+00:00 phase=2 -->
### p2-queue-opens-on-first-ready · decision · The wave queue opens only once the wave's first entry is ready (phase 2)

Spec §B's 'the queue still opens on its first ready entry' means: an idle repo chooses the lowest wave with a non-terminal batch and opens its queue only when an entry of that wave is ready. While none is, no queue opens and no hold is written, so a wave still in development never blocks a release; a later wave's ready PRs wait as before (R2). Pinned by tests/unit/test_wave_queue_planner.py::test_an_idle_repo_opens_nothing_while_no_entry_of_the_lowest_unfinished_wave_is_ready and ::test_an_idle_repo_opens_the_lowest_unfinished_wave_on_its_first_ready_entry; spec §B reworded to say so.

<!-- fr:journal kind=review scope=plan id=p2-review-1 created=2026-11-20T09:41:53+00:00 phase=2 -->
### p2-review-1 · review · Phase 2 review — four reviewer findings plus two raised in fixing, all in scope, all fixed (phase 2)

An independent reviewer read the planner diff (4d27bd0f1..7a39c6c67) against R1–R36. It confirmed
prefix and depth, R13's one rebuild per tree, wave exclusivity and the hold, the R36 cap exemption,
purity, the report-only wiring, and that removing reupdate kept approval voiding, the conflict and
red budgets and version slots. It raised p2-r1..p2-r4 and a spec reading (filed by the orchestrator
as p2-r5); the fix round found p2-r6. Fixes are b03614fc5..da7300a6e. The full suite after p2-r1..r5
passed (16966 passed, 122 skipped); p2-r6 is a pure planner change covered by the 54 wave-queue tests,
and deliver's full suite covers it.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-20T09:41:53+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · a conflict-ejected entry re-entered at the same head on the next pass (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-20T09:41:53+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · a foreign move of main with an empty window left the queue open forever (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-20T09:41:53+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · queue-build's fresh flag marked every entry, not only the R13 same-tree retry (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-20T09:41:53+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · QueuePlan.waiting listed open-wave entries ejected at an unchanged head (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-20T09:41:53+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · an idle repo opened the lowest wave's queue before any entry was ready, holding releases for the wave's whole development (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-20T09:41:53+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · a between-waves queue whose only entry was ejected, with nothing landed, never drained (phase 2)

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-20T09:41:53+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: a conflict-ejected entry re-entered at the same head on the next pass (phase 2)

QueueEjectEvent and the eject action carry the head left at, with a fallback to the batch's conflict event; tests in test_wave_queue_planner.py (no re-entry at an unchanged head, no duplicate eject, re-entry once the head moves).

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-20T09:41:53+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: a foreign move of main with an empty window left the queue open forever (phase 2)

with nothing to rebuild, a foreign move adopts the moved main; every open pass ends in a shared _tail deciding drain or R30 stall; tests drain at the moved main and still propose the stalled batch.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-20T09:41:53+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: queue-build's fresh flag marked every entry, not only the R13 same-tree retry (phase 2)

QueueAction.fresh became fresh_entry naming the one retried entry; test at depth 3 shows only b fresh.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-20T09:41:53+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: QueuePlan.waiting listed open-wave entries ejected at an unchanged head (phase 2)

ejected-at-head entries of the open wave are excluded from waiting and entries; tests for conflict and red ejection.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-20T09:41:53+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: an idle repo opened the lowest wave's queue before any entry was ready, holding releases for the wave's whole development (phase 2)

_plan_idle opens nothing while no entry of the lowest unfinished wave is ready; spec §B reworded; decision p2-queue-opens-on-first-ready; tests for both cases.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-20T09:41:53+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: a between-waves queue whose only entry was ejected, with nothing landed, never drained (phase 2)

a between-waves queue drains at its base once nothing is left to land (R29/R17 support drain, not clear); an entry ejected from an earlier between-waves queue at its live head opens no new queue until its head moves; spec §B reworded; four planner tests.

<!-- fr:journal kind=discovery scope=plan id=p3-suite-evidence-tmpdir created=2026-11-20T11:54:35+00:00 phase=3 -->
### p3-suite-evidence-tmpdir · discovery · fr's tests-log witness does not expand $TMPDIR, so phase 3's suite log is left out (phase 3)

The executor's full suite passed (17014 passed, 122 skipped, exit 0) into `$TMPDIR/wave-p3-suite.log`.
`fr run resolve` refuses the expanded path as written by no command of the holder: the witness
matches the literal redirect target and does not expand `$TMPDIR`. The log is left out of the record;
deliver's own full suite covers this phase. Worth an fr fix (out of this feature's scope).

<!-- fr:journal kind=decision scope=plan id=p3-open-drain-record-only created=2026-11-20T11:54:35+00:00 phase=3 -->
### p3-open-drain-record-only · decision · queue-open and queue-drain only record their events in phase 3; the hold pushes are phase 4's (phase 3)

The executor records `queue_open` (a new QueueRecord at main's sha) and `queue_drain`
through the one writer, so the queue runs end to end, but writes no
`refs/heads/fr-hold/queue`; `queue-hold` and `queue-cleared` print "planned, not executed
(the hold is not written yet)". Phase 4 adds the leased hold pushes to these two actions.
No repo has a `queue:` block until phase 7, so nothing changes behaviour in between.

<!-- fr:journal kind=decision scope=plan id=p3-gating-in-the-command created=2026-11-20T11:54:35+00:00 phase=3 -->
### p3-gating-in-the-command · decision · Refusals, slot-check Needs and landing pauses are applied to the plan by the command, not in batch_drive (phase 3)

batch_drive.py is outside phase 3's file list, so `drive_pass` is unchanged: the command
post-processes `Pass.queues` (`held_plan` for no queue.ci / ci: none with CI / a glab or
tea client; queue-need for a required check that never reported; `QueueExecutor.gate`
for post_merge (R33) and the forge read-back (R35)) and prints those reports itself via
`_report_once`. It also drops `drive_pass`'s per-batch `post-merge` actions for queue
repos: the queue runs post_merge once per landing (`_post_merge(..., also=...)` records
it on every landed batch).

<!-- fr:journal kind=decision scope=plan id=p3-queue-built-before-push-resume created=2026-11-20T11:54:35+00:00 phase=3 -->
### p3-queue-built-before-push-resume · decision · queue_built is recorded before each slot push, so resume re-pushes a recorded combination (phase 3)

As the plan says, `queue_built` is written before the slot push. A driver killed between
the two leaves a recorded sha the slot lacks; `QueueExecutor.resume` re-pushes it
(leased on what the slot holds) when the clone has the commit. A landing pushed but not
recorded is recognised by `main` equal to a recorded combination's sha and recorded as
`queue_land`, never pushed again (R24). A recorded combination whose commit is on no
clone the driver has (another host built it) stays pending until rebuilt.

<!-- fr:journal kind=decision scope=plan id=p3-facts-schema-16 created=2026-11-20T11:54:35+00:00 phase=3 -->
### p3-facts-schema-16 · decision · TriageConfig.queue moves the facts stamp to 16 (phase 3)

`Facts.to_json` dumps every config, `queue: null` included, which a closed-world
schema-15 reader rejects, so FACTS_SCHEMA is 16 (15 is released); the four scenario
fixture generators were re-run.

<!-- fr:journal kind=discovery scope=plan id=p3-rebase-version-conflicts created=2026-11-20T11:54:35+00:00 phase=3 -->
### p3-rebase-version-conflicts · discovery · Under rebase, R6's version rule is applied per replayed commit (phase 3)

`rebase` cherry-picks the PR's non-merge commits onto the combination; a conflicted pick
is resolved by the same `unresolvable` rule over the PR's whole change (taking the
combination's side), and the slot version is folded into the last replayed commit. A PR
whose history contains merges of main may conflict where its tree would not; that is a
real conflict, handed back.

<!-- fr:journal kind=decision scope=plan id=p3-queue-push-site-pinned created=2026-11-20T11:54:35+00:00 phase=3 -->
### p3-queue-push-site-pinned · decision · Checkout.push_leased is pinned as its own git push site, not routed through push_product_branch (phase 3)

tests/unit/test_tripwire_product_push.py pins every git push site. The queue's landing
pushes the default branch, but it carries approved, tested PR content (the forge
merge's job done by push), not fr's own files, so the placement scan of
push_product_branch does not apply; it is allowlisted as QUEUE_PUSHERS with that
argument. The slot pushes go through the same method.

<!-- fr:journal kind=lens scope=plan id=lens-security-2 created=2026-11-20T11:54:35+00:00 phase=3 lens=security step=implement-phase -->
### lens-security-2 · lens · The driver now pushes the default branch directly (atomic, leased) and rewrites PR head refs under squash and rebase (phase 3)

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-20T11:54:35+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

build was written once against the refactored batch_merge.unresolvable (split out of _unresolvable in the same commit) and Worktree.stage (split out of commit_all); no second copy left to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-20T11:54:35+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

land_push, land_merge and read_back share Landing/LandResult from the start; the refusal wording lives in one refusal_reason; nothing duplicated

<!-- fr:journal kind=review scope=plan id=p3-review-1 created=2026-11-20T13:25:52+00:00 phase=3 -->
### p3-review-1 · review · Phase 3 review — nine in-scope findings fixed, one out-of-scope refuted (phase 3)

An independent reviewer read the executor diff (df23637..feede7110) against R1–R36. It confirmed the
lease design (main leased on the tested base, each PR head on its recorded head, main moved to the
tested sha), --atomic with no fallback, the squash chain, post_merge once per landing, the two land:push
crash windows, and glab/tea held. It raised p3-r1..p3-r9 (in) and p3-r10 (out). Fixes are
fc8ec0c82..45344b0c7, adding schema-13 events queue_halt and queue_slot_lost (spec R11, R24).
The full suite after the fixes: 17043 passed, 1 failed, 122 skipped; the one failure,
tests/integration/test_scenarios.py::test_placement_move_and_drift (fr placement move refused over an
uncommitted fixture file under its own tmp HOME), passes alone (rerun by the orchestrator: 1 passed)
and this round touched no placement code: a flake under load. deliver's full suite re-checks it.

<!-- fr:journal kind=discovery scope=plan id=p3-halt-needs-operator-retry created=2026-11-20T13:25:52+00:00 phase=3 -->
### p3-halt-needs-operator-retry · discovery · no command clears a queue_halt; phase 7's operator verbs should add an explicit retry (phase 3)

A halt lifts only when queue.land changes or the default branch moves, so an operator who fixes a
ruleset or an "up to date" rule has nothing to act with. Phase 7 (defer/requeue and the operator view)
adds an explicit retry verb that records the halt as lifted.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-20T13:25:52+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · land:merge stops and land:push holds were never persisted, so the next pass landed again and R34 never reached Needs you (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-20T13:25:52+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · land:merge with a version block always failed the tree check after merging every PR (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-20T13:25:52+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · resume recorded an unrecorded landing only when main equalled a combination sha, wedging the queue (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-20T13:25:52+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · a landed PR still reading OPEN had its approval voided and approved-fr removed (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-11-20T13:25:52+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · the command-level executor wiring had no test through fr triage batch drive (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-11-20T13:25:52+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · the push tripwire allowlisted the generic Checkout.push_leased with no caller pin (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-11-20T13:25:52+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · the landing did not enforce that the tip fast-forwards main (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r8 created=2026-11-20T13:25:52+00:00 phase=3 state=open review_scope=in -->
### p3-r8 · finding [open] (reviewer: in scope) · slot leases read ls-remote at build time and resume re-pushed over a detected writer (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r9 created=2026-11-20T13:25:52+00:00 phase=3 state=open review_scope=in -->
### p3-r9 · finding [open] (reviewer: in scope) · rebase replay with --no-merges silently dropped content living only in a PR's merge commits (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r10 created=2026-11-20T13:25:52+00:00 phase=3 state=open review_scope=out -->
### p3-r10 · finding [open] (reviewer: out of scope) · origins facts compared against FACTS_SCHEMA by equality, possibly stranded by the facts bump (phase 3)

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-20T13:25:52+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: land:merge stops and land:push holds were never persisted, so the next pass landed again and R34 never reached Needs you (phase 3)

_land records queue_halt on held/stopped; the planner's live_halt/_halted turn the plan into one queue-need (Needs you) and nothing builds or lands until queue.land changes or main moves; tests in test_queue_resume.py and test_wave_queue_planner.py.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-20T13:25:52+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: land:merge with a version block always failed the tree check after merging every PR (phase 3)

queue_refusal refuses land:merge with a version block, naming both and suggesting queue.land push; spec R11 says so; test_queue_exec.py.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-20T13:25:52+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: resume recorded an unrecorded landing only when main equalled a combination sha, wedging the queue (phase 3)

_resume_landing records the deepest recorded combination that is an ancestor of main (push) or reads the PRs back from the forge (merge), halting on an untested tree; tests for a foreign move after an unrecorded push and kills mid and after forge merges.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-20T13:25:52+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: a landed PR still reading OPEN had its approval voided and approved-fr removed (phase 3)

queue_landed gives the landed batches; settle_approvals and pr_open_queue skip them; tests in test_triage_approval.py and test_queue_drive_cmd.py (fails without the wiring).

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-11-20T13:25:52+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: the command-level executor wiring had no test through fr triage batch drive (phase 3)

new tests/integration/test_queue_drive_cmd.py drives the real command over a real bare origin; build, one-push landing, post_merge once, resume after a killed driver, the failure mapping and no-post_merge landing.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-11-20T13:25:52+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: the push tripwire allowlisted the generic Checkout.push_leased with no caller pin (phase 3)

test_tripwire_product_push.py pins every push_leased caller by module and function and atomic=True only in land_push, with a scanner self-test.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-11-20T13:25:52+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: the landing did not enforce that the tip fast-forwards main (phase 3)

land_push holds unless the bottom parent is the base and base is an ancestor of the tip, persisted as a halt; tests in test_queue_land.py.

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved created=2026-11-20T13:25:52+00:00 phase=3 state=fixed resolves=p3-r8 -->
### p3-r8-resolved · finding [fixed] · resolves p3-r8: slot leases read ls-remote at build time and resume re-pushed over a detected writer (phase 3)

slot_leases gives the last recorded sha per slot; builds lease on it; a lost lease is recorded as queue_slot_lost and resume never re-pushes over it; tests in test_queue_resume.py, test_queue_build.py and the planner.

<!-- fr:journal kind=finding scope=plan id=p3-r9-resolved created=2026-11-20T13:25:52+00:00 phase=3 state=fixed resolves=p3-r9 -->
### p3-r9-resolved · finding [fixed] · resolves p3-r9: rebase replay with --no-merges silently dropped content living only in a PR's merge commits (phase 3)

_keeps_merge_content compares the replayed tree with a plain merge and ejects with "rebase would drop content from its merge commits"; real evil-merge test in test_queue_build.py.

<!-- fr:journal kind=finding scope=plan id=p3-r10-resolved created=2026-11-20T13:25:52+00:00 phase=3 state=refuted resolves=p3-r10 -->
### p3-r10-resolved · finding [refuted] · resolves p3-r10: origins facts compared against FACTS_SCHEMA by equality, possibly stranded by the facts bump (phase 3)

origins.py:311 compares against origins.py's own FACTS_SCHEMA = 1 (line 74, the origins-facts.json stamp), not fr.triage.model.FACTS_SCHEMA, which origins never imports; the bump to 16 leaves cached origins facts readable.

<!-- fr:journal kind=decision scope=plan id=p4-hold-record-first created=2026-11-20T14:32:32+00:00 phase=4 -->
### p4-hold-record-first · decision · The queue records queue_open and queue_drain before pushing the hold, and the planner repairs either crash window (phase 4) (phase 4)

queue_open and queue_drain are recorded first, then the leased hold push follows. An open queue
whose hold push failed or never ran has no hold, which R27's re-arm repairs on the next pass.
A drain recorded whose `drained` push never ran leaves our `open` hold with a drained record:
`_after_drain` plans a `queue-drain` again, which re-pushes the hold and records nothing twice.
Before recording an open the executor reads the hold and opens nothing under another scope's.

<!-- fr:journal kind=decision scope=plan id=p4-hold-refresh-hourly created=2026-11-20T14:32:32+00:00 phase=4 -->
### p4-hold-refresh-hourly · decision · An open hold is refreshed once it is an hour old, not on every pass (phase 4) (phase 4)

R17 says the driver refreshes the hold each pass. Every push to fr-hold/** starts a release.yml
run (R19), so a refresh per drive pass would start a run a minute. The planner emits
`queue-hold` (refresh) once `refreshed` is HOLD_REFRESH_AFTER (1 hour) old, well inside R18's
24 hours. A departure from the letter of R17, not its purpose.

<!-- fr:journal kind=decision scope=plan id=p4-hold-read-gates-the-rules created=2026-11-20T14:32:32+00:00 phase=4 -->
### p4-hold-read-gates-the-rules · decision · Hold rules apply only to a snapshot that read the hold (QueueSnapshot.hold_read) (phase 4) (phase 4)

None cannot mean both "absent" and "not read". `hold_read` (the Snapshot's `queue_holds` carries
a key per repo it read) switches on the re-arm, refresh and drained-clear rules, so a pass that
could not read the hold (said once) writes none of them and the existing planner tests, which
pass no hold, are unchanged. A ref that is no hold message reads as an open hold of scope
`unreadable`: it holds the queue and every release until someone clears it.

<!-- fr:journal kind=decision scope=plan id=p4-version-run-held-exits-nonzero created=2026-11-20T14:32:32+00:00 phase=4 -->
### p4-version-run-held-exits-nonzero · decision · A held --version run exits non-zero, printing the clear command and the re-dispatch (phase 4) (phase 4)

R18 says a `--version` run is held too and prints how to clear the hold by hand. No later run
carries the override, so, like a superseded one, it exits non-zero (EXIT_REFUSED) and names
`git push origin --delete fr-hold/queue` and `gh workflow run release.yml -f version=X`.
A run without the override that is held exits 0 and, in the job graph, reports cut=false.

<!-- fr:journal kind=decision scope=plan id=p4-clear-after-every-finished-run created=2026-11-20T14:32:32+00:00 phase=4 -->
### p4-clear-after-every-finished-run · decision · release.py clears a drained hold after publish, and after any run that cuts nothing (phase 4) (phase 4)

`_finish_and_clear` is the last step of publish (the push landed or was already there) and of
the prepare/no-cut path, including "no pending fragments" and "nothing installable": a drain
with only docs would otherwise stay drained until the operator cleared it. The clear is
`--force-with-lease=<ref>:<drained sha>` of a `cleared` commit on the drained main's tree, and
only when the run's HEAD contains the hold's parent. A superseded or failed run never reaches it.
Fetching the hold is credential-free; a failed fetch other than "no such ref" refuses the run.

<!-- fr:journal kind=discovery scope=plan id=p4-fr-release-status-reads-the-hold-too created=2026-11-20T14:32:32+00:00 phase=4 -->
### p4-fr-release-status-reads-the-hold-too · discovery · fr release status (the forge path) also reads the hold from origin (phase 4) (phase 4)

`--from-json` takes the hold from release.py's facts; the plain command reads it with
`read_hold` over this checkout, so an operator sees the same verdict. The JSON stays schema 1
with two additive keys, `held` and `warnings`, which release.py's reader ignores.

<!-- fr:journal kind=discovery scope=plan id=p4-stale-wave-exclusive-ref created=2026-11-20T14:32:32+00:00 phase=4 -->
### p4-stale-wave-exclusive-ref · discovery · The wave-queue-wave-exclusive row cited a test phase 2's review renamed (phase 4) (phase 4)

`fr acceptance check` named the old test name as unresolved; repointed to
test_an_idle_repo_opens_the_lowest_unfinished_wave_on_its_first_ready_entry. The check still
reports the git-answers-cached, scenario-tier and fast-tier rows of main (behind main).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-11-20T14:32:32+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

the hold read and write went into queue_exec once (read_hold, push_hold, _hold_write); open, refresh, re-arm, drain and clear all share them, so nothing was duplicated to clean

<!-- fr:journal kind=review scope=plan id=p4-review-1 created=2026-11-20T16:25:17+00:00 phase=4 -->
### p4-review-1 · review · Phase 4 review — eight in-scope findings, all fixed (phase 4)

An independent reviewer read the hold-handshake diff (da39227..ea991ddcd) against R17–R19, R27, R31,
§G and §K and AGENTS.md's release invariants. It confirmed every cutting path checks the hold, the
hold read fails closed, the clear is drained-only and leased on the sha read, credentials stay scoped
to the jobs holding GH_TOKEN, and the tripwire pin adds exactly push_hold. It raised p4-r1..p4-r8.
Fixes are 9f6b70339..062bbcb86: every hold write is a merge commit (first parent keeps its spec
meaning, second the hold it replaces), so each write fast-forwards; a refused hold write is a halt
with a Need. Full suite after the fixes: 17116 passed, 122 skipped, exit 0.

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-11-20T16:25:17+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · refused hold pushes (every later write non-fast-forward) were only a pass line, letting the hold go stale and a refused drained push wedge the repo (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-11-20T16:25:17+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · release.yml ran prepare on every push to fr-hold/**, not only drained (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-11-20T16:25:17+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · publish did not re-check the hold before pushing (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-11-20T16:25:17+00:00 phase=4 state=open review_scope=in -->
### p4-r4 · finding [open] (reviewer: in scope) · _finish_and_clear cleared after finish returned EXIT_FLOOR, a failed run (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-11-20T16:25:17+00:00 phase=4 state=open review_scope=in -->
### p4-r5 · finding [open] (reviewer: in scope) · fr release status failed open on an unreadable hold (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r6 created=2026-11-20T16:25:17+00:00 phase=4 state=open review_scope=in -->
### p4-r6 · finding [open] (reviewer: in scope) · AGENTS.md still said two pushes authenticate; the cleared-hold push is a third (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r7 created=2026-11-20T16:25:17+00:00 phase=4 state=open review_scope=in -->
### p4-r7 · finding [open] (reviewer: in scope) · a naive refreshed stamp raised TypeError reported as a malformed PR record (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r8 created=2026-11-20T16:25:17+00:00 phase=4 state=open review_scope=in -->
### p4-r8 · finding [open] (reviewer: in scope) · no test for a remote-refused hold push or the race between the free check and the leased write (phase 4)

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-11-20T16:25:17+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: refused hold pushes (every later write non-fast-forward) were only a pass line, letting the hold go stale and a refused drained push wedge the repo (phase 4)

hold writes are merge commits via Checkout.ref_commit(previous=) (driver and release.py), readers take the first parent; a refused write is a queue_halt ("hold write refused") that stops landing with a Need until a write succeeds, and refused drained/cleared writes are Needs; spec R17/§G updated; tests under a no-force-push hook in test_queue_hold.py, planner and release-script tests.

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-11-20T16:25:17+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: release.yml ran prepare on every push to fr-hold/**, not only drained (phase 4)

prepare's if runs an fr-hold push only when its head commit starts 'fr-hold: drained'; deletion guard kept; test_release_workflow.py evaluates the expression per case.

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-11-20T16:25:17+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: publish did not re-check the hold before pushing (phase 4)

publish re-runs check_hold before push; held prints nothing is pushed and clears nothing; test_release_script.py.

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-11-20T16:25:17+00:00 phase=4 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: _finish_and_clear cleared after finish returned EXIT_FLOOR, a failed run (phase 4)

_finish_and_clear clears only on EXIT_OK; docstring fixed; test_a_run_the_floor_check_fails_clears_nothing.

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-11-20T16:25:17+00:00 phase=4 state=fixed resolves=p4-r5 -->
### p4-r5-resolved · finding [fixed] · resolves p4-r5: fr release status failed open on an unreadable hold (phase 4)

_hold_facts returns the unread reason; status reports hold_unknown and "no final can be confirmed"; tests in test_release_status.py.

<!-- fr:journal kind=finding scope=plan id=p4-r6-resolved created=2026-11-20T16:25:17+00:00 phase=4 state=fixed resolves=p4-r6 -->
### p4-r6-resolved · finding [fixed] · resolves p4-r6: AGENTS.md still said two pushes authenticate; the cleared-hold push is a third (phase 4)

AGENTS.md, release.py's docstring and docs/merge-protection.md name the leased cleared-hold push as a third authenticated push; the hold fetch stays credential-free.

<!-- fr:journal kind=finding scope=plan id=p4-r7-resolved created=2026-11-20T16:25:17+00:00 phase=4 state=fixed resolves=p4-r7 -->
### p4-r7-resolved · finding [fixed] · resolves p4-r7: a naive refreshed stamp raised TypeError reported as a malformed PR record (phase 4)

hold_verdict treats a naive or unparseable stamp as an unreadable hold that holds, with a warning; tests in test_release_status.py.

<!-- fr:journal kind=finding scope=plan id=p4-r8-resolved created=2026-11-20T16:25:17+00:00 phase=4 state=fixed resolves=p4-r8 -->
### p4-r8-resolved · finding [fixed] · resolves p4-r8: no test for a remote-refused hold push or the race between the free check and the leased write (phase 4)

test_queue_hold.py covers a remote refusing hold pushes and a writer taking the hold between the check and the lease (lease fails, nothing lands, reported as queue-held naming the other scope).
