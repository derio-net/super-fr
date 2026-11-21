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

<!-- fr:journal kind=decision scope=plan id=p5-fr-update-branch-read-only created=2026-11-20T19:35:29+00:00 phase=5 -->
### p5-fr-update-branch-read-only · decision · The fr-update branch of the approval verdict stays, read-only, for stored judgements (supersedes p1-fr-updates-keep-approval's carry-over for new work) (phase 5)

With the train and the update path gone nothing writes an `update` event, so no new approval can ever
be carried across an fr update. The branch of `approval_verdict` that follows `reaches()` over
UpdateEvents is unreachable for anything written after this change, but a `judgements.yaml` written
before it still holds approvals recorded without a patch-id and the updates that followed them, and
a PR open on one of them must judge as it did. `reaches`, `UpdateEvent.patch_id` and
`_pinned_ids` are therefore kept as readers only (docstring says so); the writers are removed:
`update_recorder`, `MergeContext.on_update` and `recorded`, `_dequeue_unapproved` and its enqueue
event. p1-fr-updates-record-patch-id described a behaviour that no longer exists; its reading stays.

<!-- fr:journal kind=decision scope=plan id=p5-every-repo-is-a-queue-repo created=2026-11-20T19:35:29+00:00 phase=5 -->
### p5-every-repo-is-a-queue-repo · decision · A repo with no `queue:` block gets the default block, whose `ci` is unset, so the queue refuses it and says what to add (phase 5)

There is no train to fall back to, so `_Driver._queue_block` returns `QueueBlock()` for a repo with
none and `queue_refusal` (R7) holds it with "add ci: push under queue:". `Snapshot.wave_queues` lists
every repo. The tests that drove the train with no config now run on a `RecordingQueue` executor
stand-in (the real one runs over real git in tests/integration/test_queue_drive_cmd.py).
A base whose `base_rules().merge_queue` is true is held first, before any `queue.ci` complaint,
because no setting of fr's queue makes it work (R22).

<!-- fr:journal kind=decision scope=plan id=p5-other-entries-are-admitted-not-merged created=2026-11-20T19:35:29+00:00 phase=5 -->
### p5-other-entries-are-admitted-not-merged · decision · The pure pass admits a non-batch PR under its trust rule (`Admitted`); the queue plans, builds and lands it (phase 5)

`_collected_step` (review_reasons empty), the attributed archive PR (`archive_allowed`) and
`_export_row` (the recorded head) return `Admitted`; a housekeeping PR (`chore/ops-<slug>`) is
admitted by the command only with `approved-fr` recorded as a queue `approval`
(`approval.settle_entry_approval`, the batch rule: pinned to the patch-id, void on a diff change).
`wave_queue.OtherEntry` carries it into the planner, `<kind>#<pr>` is its key, a close-out is
always the last entry of its wave (R15) and joins the open wave's queue, every other kind queues
between waves (R2, R32). `_archive` and `_export_merge` are deleted; the forge merge stays only
behind `land: merge`. Nothing a later pass needs is lost: `closeout-merged` and `export-reconcile`
record a landed PR the forge reads MERGED, and an attributed archive PR, which could not be found
again once it left the open list, is recorded by `QueuePorts.landed` at the landing (rg-6).

<!-- fr:journal kind=decision scope=plan id=p5-wave-drain-waits-on-the-closeout created=2026-11-20T19:35:29+00:00 phase=5 -->
### p5-wave-drain-waits-on-the-closeout · decision · A wave drains once its ungated landed batches are closed out; a stalled close-out is a Need (phase 5)

R15 says the queue does not drain until the wave's close-out landed. `batch_drive.wave_closeout_landed`
derives it from the batches (landed, not gated, not archived, not held by the verb, closeout event
with `archived` or its collected PR landed by the queue) and `Snapshot.queue_closeouts` still
overrides it. `wave_queue._closeout_need` says, after `stall_hours` with nothing left to land,
that the hold stays open on the close-out. The driver does not know a repo's placement (it starts
close-outs for every repo today), so the wait is uniform: the spec's "under quiet or stealth the
queue holds batch PRs only" is not applied (see p5-driver-has-no-placement).

<!-- fr:journal kind=discovery scope=plan id=p5-driver-has-no-placement created=2026-11-20T19:35:29+00:00 phase=5 -->
### p5-driver-has-no-placement · discovery · The triage driver has no notion of placement, so R15's repo-placement condition on the close-out entry is not enforced (phase 5)

grep finds no `placement` in `fr/triage/batch_drive.py` or `commands/triage_batch_cmd.py`: close-outs
are collected for every repo whatever keeps its artifacts. A quiet or stealth repo therefore waits
on its close-out before a wave drains, and its close-out PR, if any, is a queue entry. Whether a
close-out exists there at all is the close-out verb's, not the queue's. Left to phase 6, which owns
R15's gating; the Need above makes a stuck wave visible.

<!-- fr:journal kind=decision scope=plan id=p5-batch-merge-is-the-driver-with-the-queue-only created=2026-11-20T19:35:29+00:00 phase=5 -->
### p5-batch-merge-is-the-driver-with-the-queue-only · decision · `batch merge` runs the driver's own pass in the foreground with every action but the queue's dropped (phase 5)

R23. `batch_merge_command` builds a `_Driver` with `queue_only=True` (its plan keeps only the held,
blocked and warn reports, the red hand-back included) and `method_override`, takes the drive lock
under `--yes`, and loops `run_pass` until every named or pr-open batch landed, is not ready (no
approval, red, held by a gate, waiting on a later wave's queue) or a pass reported a held queue
or a Need (exit 1). It polls every 30 s and gives up after an hour of nothing changing. Without
`--yes` it prints the one pass's plan. A named batch without a valid approval is still refused
(exit 2) after the pass settled approvals. The queue is left open for the rest of its wave.

<!-- fr:journal kind=discovery scope=plan id=p5-train-scenarios-ported-or-trimmed created=2026-11-20T19:35:29+00:00 phase=5 -->
### p5-train-scenarios-ported-or-trimmed · discovery · The four train scenarios were trimmed to what the queue keeps, and the real-git `batch merge` test is gone (phase 5)

merge-train-label-gate.sh keeps the label, the void and the board asks (four passes); merge-train-red-recovery.sh
keeps the hand-back phases and reads an old `update` event; merge-train-queue.sh now proves the
forge-queue hold and the `queue.ci` refusal; batch-merge-skip-held.sh keeps the skip and the refusal.
tests/integration/test_triage_batch_merge_git.py and test_triage_merge_routine_git.py tested the
update path and the strict-checks exemption, which are gone; the queue's own real-git tests cover
version slots, relock and conflicts. Acceptance rows amended: five retired, six reworded or
re-pointed (fr acceptance amend), wave-queue-one-path moved to ci.

<!-- fr:journal kind=discovery scope=plan id=p5-clients-lost-enqueue created=2026-11-20T19:35:29+00:00 phase=5 -->
### p5-clients-lost-enqueue · discovery · GhClient lost pr_enqueue, pr_dequeue, pr_queue_state and QueueState (phase 5)

Their only callers were the enqueue executor and `_dequeue_unapproved`; `grep -rn "pr_enqueue\|_walk_queue\|merge_ready" packages/`
now returns nothing. The forge_guard and archive_preview method lists and the gitseam methods only
the update path used (`commits_behind`, `take_theirs`, `commit_all`) went with them. `BaseRules.merge_queue`
stays: it is the R22 hold's input.

<!-- fr:journal kind=lens scope=plan id=lens-security-3 created=2026-11-20T19:35:29+00:00 phase=5 lens=security step=implement-phase -->
### lens-security-3 · lens · The driver now admits non-batch PRs to a queue that lands them by push, on trust rules the old merge step applied (phase 5)

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t1 created=2026-11-20T19:35:29+00:00 phase=5 -->
### no-refactor-p5-t1 · discovery · no-refactor-because P5.T1 (phase 5)

the three admission paths (a collected close-out, an attributed archive PR, an export PR) each returned an Action already; they return one Admitted type instead and nothing was duplicated, so there was nothing to clean

<!-- fr:journal kind=review scope=plan id=p5-review-1 created=2026-11-20T21:31:46+00:00 phase=5 -->
### p5-review-1 · review · Phase 5 review — seven in-scope findings and one out-of-scope, all fixed (phase 5)

An independent reviewer read the one-merge-path diff (0fa9fa1..3f73c4bf9) against R1–R36. It confirmed
stored events still load (UpdateEvent and EnqueueEvent stay in the union), approval voiding, the conflict
and red budgets, version slots, gate labels, Closes unlabelling and post_merge survive on the queue path,
and that other features' rows changed only by amendment. It raised p5-r1..p5-r7 (in) and p5-r8 (out,
fixed with p5-r4). Fixes are 1f18c4f2d..571c8345f; full suite after them: 16950 passed, 122 skipped.

<!-- fr:journal kind=decision scope=plan id=p5-major-bump created=2026-11-20T21:31:46+00:00 phase=5 -->
### p5-major-bump · decision · The change fragment is bump major, because a consumer's driver merges nothing until it adds a queue block (phase 5)

R7/R22 refuse a repo with no queue.ci, so on upgrade every consumer's wave driver holds every merge until
.fr/triage.yaml gains `queue: {ci: push|none}` and CI runs on `fr-queue/**`. That is a breaking behaviour
change for consumers, so the fragment is major, its summary says so, and the wave-driver page carries the
migration note. The operator may lower it at the PR.

<!-- fr:journal kind=finding scope=plan id=p5-r1 created=2026-11-20T21:31:46+00:00 phase=5 state=open review_scope=in -->
### p5-r1 · finding [open] (reviewer: in scope) · approved green draft batch PRs were never marked ready by the queue (phase 5)

<!-- fr:journal kind=finding scope=plan id=p5-r2 created=2026-11-20T21:31:46+00:00 phase=5 state=open review_scope=in -->
### p5-r2 · finding [open] (reviewer: in scope) · a consumer repo with no queue block silently stopped merging, with no Need, a board saying merge ready, and a minor fragment (phase 5)

<!-- fr:journal kind=finding scope=plan id=p5-r3 created=2026-11-20T21:31:46+00:00 phase=5 state=open review_scope=in -->
### p5-r3 · finding [open] (reviewer: in scope) · an ejected close-out or archive entry lost its session hand-back (phase 5)

<!-- fr:journal kind=finding scope=plan id=p5-r4 created=2026-11-20T21:31:46+00:00 phase=5 state=open review_scope=in -->
### p5-r4 · finding [open] (reviewer: in scope) · housekeeping admission never checked the PR's base branch (phase 5)

<!-- fr:journal kind=finding scope=plan id=p5-r5 created=2026-11-20T21:31:46+00:00 phase=5 state=open review_scope=in -->
### p5-r5 · finding [open] (reviewer: in scope) · dead MergeContext fields rules, patch_id_of and say were written and never read (phase 5)

<!-- fr:journal kind=finding scope=plan id=p5-r6 created=2026-11-20T21:31:46+00:00 phase=5 state=open review_scope=in -->
### p5-r6 · finding [open] (reviewer: in scope) · --order help and the Batches page still called order a hard merge constraint (phase 5)

<!-- fr:journal kind=finding scope=plan id=p5-r7 created=2026-11-20T21:31:46+00:00 phase=5 state=open review_scope=in -->
### p5-r7 · finding [open] (reviewer: in scope) · docs left stale by the phase (fr-triage explainer, index stamp, herdr page, skill event list) (phase 5)

<!-- fr:journal kind=finding scope=plan id=p5-r8 created=2026-11-20T21:31:46+00:00 phase=5 state=open review_scope=out -->
### p5-r8 · finding [open] (reviewer: out of scope) · batch entries were never base-checked before a push landing (phase 3's executor) (phase 5)

<!-- fr:journal kind=finding scope=plan id=p5-r1-resolved created=2026-11-20T21:31:46+00:00 phase=5 state=fixed resolves=p5-r1 -->
### p5-r1-resolved · finding [fixed] · resolves p5-r1: approved green draft batch PRs were never marked ready by the queue (phase 5)

_queue_entry readies an approved green draft batch PR when the queue builds it, both land methods; explainer and the merge-train-label-gate amendment match; test_wave_queue_phase5_fixes.py.

<!-- fr:journal kind=finding scope=plan id=p5-r2-resolved created=2026-11-20T21:31:46+00:00 phase=5 state=fixed resolves=p5-r2 -->
### p5-r2-resolved · finding [fixed] · resolves p5-r2: a consumer repo with no queue block silently stopped merging, with no Need, a board saying merge ready, and a minor fragment (phase 5)

a queue-unconfigured Need names the repo and what to add, the board shows the held reason instead of merge ready, the fragment is bump major with a rewritten summary and the wave-driver page carries the migration note (decision p5-major-bump); tests in test_wave_queue_phase5_fixes.py.

<!-- fr:journal kind=finding scope=plan id=p5-r3-resolved created=2026-11-20T21:31:46+00:00 phase=5 state=fixed resolves=p5-r3 -->
### p5-r3-resolved · finding [fixed] · resolves p5-r3: an ejected close-out or archive entry lost its session hand-back (phase 5)

_queue_hand_back_other resolves closeout#N to the collected close-out's session and archive#N to its batch's close-out session, else names the operator; tests.

<!-- fr:journal kind=finding scope=plan id=p5-r4-resolved created=2026-11-20T21:31:46+00:00 phase=5 state=fixed resolves=p5-r4 -->
### p5-r4-resolved · finding [fixed] · resolves p5-r4: housekeeping admission never checked the PR's base branch (phase 5)

wave_queue.base_refusal and _queue_entry refuse any entry whose base is not the default branch, with a Need naming the base; housekeeping test.

<!-- fr:journal kind=finding scope=plan id=p5-r5-resolved created=2026-11-20T21:31:46+00:00 phase=5 state=fixed resolves=p5-r5 -->
### p5-r5-resolved · finding [fixed] · resolves p5-r5: dead MergeContext fields rules, patch_id_of and say were written and never read (phase 5)

the dead MergeContext fields and their writes are removed.

<!-- fr:journal kind=finding scope=plan id=p5-r6-resolved created=2026-11-20T21:31:46+00:00 phase=5 state=fixed resolves=p5-r6 -->
### p5-r6-resolved · finding [fixed] · resolves p5-r6: --order help and the Batches page still called order a hard merge constraint (phase 5)

--order help and the Batches page say order breaks ties among entries ready together; tie-break test.

<!-- fr:journal kind=finding scope=plan id=p5-r7-resolved created=2026-11-20T21:31:46+00:00 phase=5 state=fixed resolves=p5-r7 -->
### p5-r7-resolved · finding [fixed] · resolves p5-r7: docs left stale by the phase (fr-triage explainer, index stamp, herdr page, skill event list) (phase 5)

fr-triage.md, index.md and herdr-control-sessions.md updated or re-stamped; the skill says update and enqueue events are read from older files and never written; mirrors synced; fr docs check current.

<!-- fr:journal kind=finding scope=plan id=p5-r8-resolved created=2026-11-20T21:31:46+00:00 phase=5 state=fixed resolves=p5-r8 -->
### p5-r8-resolved · finding [fixed] · resolves p5-r8: batch entries were never base-checked before a push landing (phase 3's executor) (phase 5)

fixed with p5-r4; batch LivePr carries base and the planner refuses a non-default base; three planner tests.

<!-- fr:journal kind=decision scope=plan id=p6-scenarios-use-journals created=2026-11-20T23:02:13+00:00 phase=6 -->
### p6-scenarios-use-journals · decision · The two scenarios stamp a journal, not a plan (phase 6) (phase 6)

The plan says "a stale-but-migratable plan stamp", but the plan kind has no registered schema
migration (`MIGRATIONS.schema_migrations("plan")` is empty): a v1 plan is unreachable, so
`--allow-migratable` rightly fails it. Both scenarios use a version-3 journal, whose 3 to 4 hop
is registered, and the validation scenario also asserts that a stale plan still fails
("no registered migration reaches").

<!-- fr:journal kind=decision scope=plan id=p6-drain-waits-on-the-barrier created=2026-11-20T23:02:13+00:00 phase=6 -->
### p6-drain-waits-on-the-barrier · decision · A wave does not drain while a landed DevOps barrier has no post-merge done (phase 6) (phase 6)

R26 says nothing lands behind a landed barrier until `queue_postmerge_done`. The planner also
holds the drain (`_tail`) while `barrier_open` names an entry, so the release does not cut an
RC before the stage's post-merge ops ran. A `Needs you` entry names `fr ops gate --run <id>`
(the run id from the entry's cursor, else `<run-id>`), said every pass until it is done.

<!-- fr:journal kind=decision scope=plan id=p6-release-void-is-an-empty-patch-id created=2026-11-20T23:02:13+00:00 phase=6 -->
### p6-release-void-is-an-empty-patch-id · decision · A voided release is a queue_release with an empty patch_id (phase 6) (phase 6)

The release label is settled like `approved-fr`: recorded at the head and patch-id (`settle_release`),
kept while the patch-id holds, and voided (label removed, a `queue_release` with an empty
patch-id recorded) when the diff moved after it, so a re-run of stage 2 that adds the label
again is a new release and not read as the stale one. No model field was added, so no stamp
moves; the model docstring says it. A `queue_release` or an `approval` may open a record of
its own before any queue opened (the writer's existing rule for housekeeping approvals).

<!-- fr:journal kind=decision scope=plan id=p6-placement-read-from-settings created=2026-11-20T23:02:13+00:00 phase=6 -->
### p6-placement-read-from-settings · decision · R15's placement condition is enforced from the clone's settings (phase 6) (phase 6)

p5-driver-has-no-placement is closed: `_placements` reads each repo's `placement` with
`load_settings` over the clone, `Snapshot.placements` carries it, and `queue_snapshot` drops the
non-batch entries and the close-out wait for a repo that is not `repo` (R15: under quiet or
stealth the queue holds batch PRs only). A repo whose settings cannot be read counts as `repo`.

<!-- fr:journal kind=decision scope=plan id=p6-method-option-removed created=2026-11-20T23:02:13+00:00 phase=6 -->
### p6-method-option-removed · decision · `fr ops gate --method` is gone: the stage merges nothing (phase 6) (phase 6)

The option picked a merge method for a merge the stage no longer makes (R26), and
`GateTarget.method` and the forge port's `repo_merge_methods` and `pr_merge` went with it. The
docs and the skill say the queue lands the PR. Stage 2 is done only when the forge reads the PR
MERGED, and the run stops (`GateResult.waiting`, exit 0) until then; a host record of stage 2
from before the queue no longer counts.

<!-- fr:journal kind=decision scope=plan id=p6-closeout-migrates-what-its-members-name created=2026-11-20T23:02:13+00:00 phase=6 -->
### p6-closeout-migrates-what-its-members-name · decision · The close-out migrates the stale artifacts that carry a member's run, plan or spec name (phase 6) (phase 6)

"Exactly the artifacts it archives" is decided by name: `CloseoutRead.scope` (run id, plan folder,
spec slug) matched as a whole path component or stem against `plan_migrations`' stale paths
(`owned_stale`). The migration is `fr migrate artifacts --yes --path ...` run in the scratch
worktree and committed with `commit_paths` as its own commit; the archive is then squashed onto
it (`squash_all(base=migration commit)`). A refused migration (a retiring hop) is undone and
the archive goes on as it always did. `review_reasons` admits `(recorded head, migration)`
when the migration commit only modifies files the recorded file set deletes.

<!-- fr:journal kind=discovery scope=plan id=p6-validate-tries-migrations-on-a-copy created=2026-11-20T23:02:13+00:00 phase=6 -->
### p6-validate-tries-migrations-on-a-copy · discovery · --allow-migratable cannot tell a refusing migration without running it (phase 6) (phase 6)

A migration refuses at apply time (a v3 journal already holding a lens entry), so `Migratable`
copies the checkout (minus .git and build dirs) once and runs every migration there, only
when some artifact is stale; the checkout is never written (a test pins the bytes).

<!-- fr:journal kind=discovery scope=plan id=p6-ops-gate-scenarios-fake-the-queue created=2026-11-20T23:02:13+00:00 phase=6 -->
### p6-ops-gate-scenarios-fake-the-queue · discovery · The two fr-ops-gate scenarios now fake the queue, not the merge (phase 6) (phase 6)

Their fake forge's `pr_merge` raises, and `edit_pr_labels` lands the PR (moves origin's main,
marks it MERGED) when `fr-queue:release` is added, as the queue would; they expect the
release prompt, not the merge one.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t1 created=2026-11-20T23:02:13+00:00 phase=6 -->
### no-refactor-p6-t1 · discovery · no-refactor-because P6.T1 (phase 6)

the DevOps stage, the settle helpers and the planner barrier were new code beside the approval settle they mirror; nothing duplicated, so nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t2 created=2026-11-20T23:02:13+00:00 phase=6 -->
### no-refactor-p6-t2 · discovery · no-refactor-because P6.T2 (phase 6)

the per-wave grouping replaced the per-repo one in the same loop and the migration commit is one new helper; nothing left over to clean

<!-- fr:journal kind=decision scope=plan id=p6-release-void-explicit created=2026-11-20T23:17:34+00:00 phase=6 -->
### p6-release-void-explicit · decision · A voided release is its own flag (voided: bool), superseding p6-release-void-is-an-empty-patch-id (phase 6)

QueueReleaseEvent gains an optional voided flag (schema 13 is unreleased, so no migration); an empty patch_id is a real release at an empty diff, and barrier_keys counts only an entry's last release when it is not voided. Chosen over a distinct event kind because the void already pins the same entry and head fields and needs no new schema-13 event registration.

<!-- fr:journal kind=review scope=plan id=p6-review-1 created=2026-11-21T00:59:28+00:00 phase=6 -->
### p6-review-1 · review · Phase 6 review — ten in-scope findings and one out-of-scope, the ten fixed (phase 6)

An independent reviewer read the gates and close-out diff against R1–R36. It confirmed the planner's
barrier (no admission without a release, nothing lands behind an open barrier, no drain while one is
open), the DevOps stage's rerun and resume, --path's refusals before any write, and the workflow
triggers. It raised p6-r1..p6-r9 and p6-r11 (in) and p6-r10 (out). Fixes are d2c45a1a8..78e3dc52d;
full suite after them: 17032 passed, 122 skipped, exit 0. Two deviations: the strict post_merge
gate is host-only (the cloud driver runs no post_merge, R20), and the --allow-migratable trial copies
the artifacts' own root rather than reproducing the placement.

<!-- fr:journal kind=finding scope=plan id=p6-r1 created=2026-11-21T00:59:28+00:00 phase=6 state=open review_scope=in -->
### p6-r1 · finding [open] (reviewer: in scope) · a release with an unreadable patch-id stayed valid at any head (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r2 created=2026-11-21T00:59:28+00:00 phase=6 state=open review_scope=in -->
### p6-r2 · finding [open] (reviewer: in scope) · the release bound to the head the driver read, not the head stage 2 checked (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r3 created=2026-11-21T00:59:28+00:00 phase=6 state=open review_scope=in -->
### p6-r3 · finding [open] (reviewer: in scope) · stage 4 never finished under forge labels off, even with the label added by hand (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r4 created=2026-11-21T00:59:28+00:00 phase=6 state=open review_scope=in -->
### p6-r4 · finding [open] (reviewer: in scope) · stage 2 stopped merging in repos no wave driver serves, with no hand-merge instruction (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r5 created=2026-11-21T00:59:28+00:00 phase=6 state=open review_scope=in -->
### p6-r5 · finding [open] (reviewer: in scope) · the change summary did not name the fr ops gate --method removal or that the DevOps stage no longer merges (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r6 created=2026-11-21T00:59:28+00:00 phase=6 state=open review_scope=in -->
### p6-r6 · finding [open] (reviewer: in scope) · a wave close-out could start before its last landing's post_merge, giving two close-outs (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r7 created=2026-11-21T00:59:28+00:00 phase=6 state=open review_scope=in -->
### p6-r7 · finding [open] (reviewer: in scope) · the close-out chose files to migrate by name, catching the acceptance fragment and missing the spec (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r8 created=2026-11-21T00:59:28+00:00 phase=6 state=open review_scope=in -->
### p6-r8 · finding [open] (reviewer: in scope) · --allow-migratable passed untried refusals under quiet and crashed under stealth (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r9 created=2026-11-21T00:59:28+00:00 phase=6 state=open review_scope=in -->
### p6-r9 · finding [open] (reviewer: in scope) · an empty patch-id meant both a voided release and a release at an empty diff (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r10 created=2026-11-21T00:59:28+00:00 phase=6 state=open review_scope=out -->
### p6-r10 · finding [open] (reviewer: out of scope) · anyone with triage permission can add the two fr-queue labels (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r11 created=2026-11-21T00:59:28+00:00 phase=6 state=open review_scope=in -->
### p6-r11 · finding [open] (reviewer: in scope) · three texts said the barrier lands alone, and a docstring misnamed the commits past the base (phase 6)

<!-- fr:journal kind=finding scope=plan id=p6-r1-resolved created=2026-11-21T00:59:28+00:00 phase=6 state=fixed resolves=p6-r1 -->
### p6-r1-resolved · finding [fixed] · resolves p6-r1: a release with an unreadable patch-id stayed valid at any head (phase 6)

settle_release keeps an unreadable-patch-id release only at its recorded head (test_queue_gate_labels.py).

<!-- fr:journal kind=finding scope=plan id=p6-r2-resolved created=2026-11-21T00:59:28+00:00 phase=6 state=fixed resolves=p6-r2 -->
### p6-r2-resolved · finding [fixed] · resolves p6-r2: the release bound to the head the driver read, not the head stage 2 checked (phase 6)

stage 2 writes the fr-queue:release marker naming head and patch-id; the driver releases only at that patch-id, from a trusted commenter.

<!-- fr:journal kind=finding scope=plan id=p6-r3-resolved created=2026-11-21T00:59:28+00:00 phase=6 state=fixed resolves=p6-r3 -->
### p6-r3-resolved · finding [fixed] · resolves p6-r3: stage 4 never finished under forge labels off, even with the label added by hand (phase 6)

stage 4 adds the label only when it is absent, then finishes.

<!-- fr:journal kind=finding scope=plan id=p6-r4-resolved created=2026-11-21T00:59:28+00:00 phase=6 state=fixed resolves=p6-r4 -->
### p6-r4-resolved · finding [fixed] · resolves p6-r4: stage 2 stopped merging in repos no wave driver serves, with no hand-merge instruction (phase 6)

with no queue config stage 2 tells the operator to merge by hand and a hand merge completes it; the gate never merges.

<!-- fr:journal kind=finding scope=plan id=p6-r5-resolved created=2026-11-21T00:59:28+00:00 phase=6 state=fixed resolves=p6-r5 -->
### p6-r5-resolved · finding [fixed] · resolves p6-r5: the change summary did not name the fr ops gate --method removal or that the DevOps stage no longer merges (phase 6)

the fragment summary names both removals; check-change-fragment passes.

<!-- fr:journal kind=finding scope=plan id=p6-r6-resolved created=2026-11-21T00:59:28+00:00 phase=6 state=fixed resolves=p6-r6 -->
### p6-r6-resolved · finding [fixed] · resolves p6-r6: a wave close-out could start before its last landing's post_merge, giving two close-outs (phase 6)

the strict gate is restored: the close-out waits for every host-run member's post_merge and starts once.

<!-- fr:journal kind=finding scope=plan id=p6-r7-resolved created=2026-11-21T00:59:28+00:00 phase=6 state=fixed resolves=p6-r7 -->
### p6-r7-resolved · finding [fixed] · resolves p6-r7: the close-out chose files to migrate by name, catching the acceptance fragment and missing the spec (phase 6)

owned_stale takes the archive's own move set (Worktree.archive_moves); real-git test added.

<!-- fr:journal kind=finding scope=plan id=p6-r8-resolved created=2026-11-21T00:59:28+00:00 phase=6 state=fixed resolves=p6-r8 -->
### p6-r8-resolved · finding [fixed] · resolves p6-r8: --allow-migratable passed untried refusals under quiet and crashed under stealth (phase 6)

the trial copies artifact_root, excludes .fr-isolation, and any trial error fails the stale artifact.

<!-- fr:journal kind=finding scope=plan id=p6-r9-resolved created=2026-11-21T00:59:28+00:00 phase=6 state=fixed resolves=p6-r9 -->
### p6-r9-resolved · finding [fixed] · resolves p6-r9: an empty patch-id meant both a voided release and a release at an empty diff (phase 6)

QueueReleaseEvent.voided is explicit (decision p6-release-void-explicit); barrier_keys counts only live releases.

<!-- fr:journal kind=finding scope=plan id=p6-r10-resolved created=2026-11-21T00:59:28+00:00 phase=6 state=open resolves=p6-r10 out_of_scope=true -->
### p6-r10-resolved · finding [out-of-scope] · resolves p6-r10: anyone with triage permission can add the two fr-queue labels (phase 6)

copies the approved-fr trust model the spec chose; not caused by this phase's shape beyond what the spec decided.

<!-- fr:journal kind=finding scope=plan id=p6-r11-resolved created=2026-11-21T00:59:28+00:00 phase=6 state=fixed resolves=p6-r11 -->
### p6-r11-resolved · finding [fixed] · resolves p6-r11: three texts said the barrier lands alone, and a docstring misnamed the commits past the base (phase 6)

the docstring and the three texts now say the barrier lands as the last entry of its push.

<!-- fr:journal kind=decision scope=plan id=p7-queue-retry-verb created=2026-11-21T02:50:37+00:00 phase=7 -->
### p7-queue-retry-verb · decision · `fr triage batch queue-retry [OWNER/REPO] [--yes]` clears a halted queue through a queue_retry event (phase 7) (phase 7)

p3-halt-needs-operator-retry: nothing cleared a `queue_halt`. The verb sits in the
defer/requeue family, prints the plan and writes only with `--yes`, and appends
`queue_retry` (a new kind in the unreleased schema 13, so no stamp moved) to the repo's
current record in the scope. Every halt before the event stops halting the queue, so the
next pass builds; a refusal that persists writes a new halt. `_last_halt` is the one
reader, so the hold-write halt is lifted by it too. The halt's Need text names the exact
command (`wave_queue.retry_command`, with the pass's scope arguments).

<!-- fr:journal kind=decision scope=plan id=p7-board-plans-the-queue-offline created=2026-11-21T02:50:37+00:00 phase=7 -->
### p7-board-plans-the-queue-offline · decision · The facts-only board now plans the wave queue from the judgements' records and the facts' config (phase 7) (phase 7)

`views.drive_snapshot` now sets `wave_queues`, `queue_records` and `scope_id`, so the
board and the Needs list see the queue's line (R25) and its Needs (R28) without a live
read: no hold, base or check is read, so a built combination reads `testing`. In a repo
with a `queue:` block an approved PR's card reads "in merge queue" where it read "merge
ready" (three board tests follow). The queue's Needs reach `needs_you` as `queue-need`
(an `Action` carrying `QUEUE_REPORT_KEY`), no longer as `blocked-batch` rows.

<!-- fr:journal kind=discovery scope=plan id=p7-acceptance-ref-renamed-in-phase-6 created=2026-11-21T02:50:37+00:00 phase=7 -->
### p7-acceptance-ref-renamed-in-phase-6 · discovery · wave-queue-wave-exclusive cited a close-out test phase 6 renamed (phase 7) (phase 7)

`fr acceptance check` failed that row's ref; it now cites
`test_the_post_merge_of_every_landing_is_planned_before_the_waves_close_out`. The
`git-answers-cached-per-invocation` refs it also lists belong to main's own row and
resolve once the branch is rebased on main.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p7-t1 created=2026-11-21T02:50:37+00:00 phase=7 -->
### no-refactor-p7-t1 · discovery · no-refactor-because P7.T1 (phase 7)

defer, requeue and queue-retry share one find, one write and one wording helper (_leavable, _wave_name); nothing was duplicated to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p7-t2 created=2026-11-21T02:50:37+00:00 phase=7 -->
### no-refactor-p7-t2 · discovery · no-refactor-because P7.T2 (phase 7)

the queue line, the board section and the pass all read one QueueView (queue_view), so the first cut had no second copy to merge

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p7-t3 created=2026-11-21T02:50:37+00:00 phase=7 -->
### no-refactor-p7-t3 · discovery · no-refactor-because P7.T3 (phase 7)

the comment bodies and the report are pure functions beside one thin sync; the driver call is one method, so there was nothing to clean

<!-- fr:journal kind=review scope=plan id=p7-review-1 created=2026-11-21T03:51:21+00:00 phase=7 -->
### p7-review-1 · review · Phase 7 review — thirteen in-scope findings, all fixed (phase 7)

An independent reviewer read the operator-view diff (2a6df2e05..e6b9d4d5b) against R1–R36. It confirmed
forge writes stay inside --yes and the GhClient, defer/requeue write through the read-compare writer,
halts are read in one place and a retry lifts only earlier halts, queue_retry is a schema 13 event, and
this repo's queue block matches the fr-queue/** and fr-hold/** triggers. It raised p7-r1..p7-r13 (all in).
Fixes are 8ba2527e5..e8450c0be; full suite after them: 17069 passed, 122 skipped, exit 0. Spec R24, R28,
R29 and §L were amended for queue_retry, plain requeue's target and the close-out report.

<!-- fr:journal kind=finding scope=plan id=p7-r1 created=2026-11-21T03:51:21+00:00 phase=7 state=open review_scope=in -->
### p7-r1 · finding [open] (reviewer: in scope) · the queue marker comment trusted any author (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r2 created=2026-11-21T03:51:21+00:00 phase=7 state=open review_scope=in -->
### p7-r2 · finding [open] (reviewer: in scope) · requeue --wave N accepted a wave whose queue had already opened and drained (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r3 created=2026-11-21T03:51:21+00:00 phase=7 state=open review_scope=in -->
### p7-r3 · finding [open] (reviewer: in scope) · queue_retry contradicted R24 and the spec was not amended (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r4 created=2026-11-21T03:51:21+00:00 phase=7 state=open review_scope=in -->
### p7-r4 · finding [open] (reviewer: in scope) · a plain requeue did not join the next queue to open, as the CLI and docs claimed (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r5 created=2026-11-21T03:51:21+00:00 phase=7 state=open review_scope=in -->
### p7-r5 · finding [open] (reviewer: in scope) · the wave report text selected records by the original wave and across scopes (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r6 created=2026-11-21T03:51:21+00:00 phase=7 state=open review_scope=in -->
### p7-r6 · finding [open] (reviewer: in scope) · the close-out PR body report predated the drain and omitted the close-out (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r7 created=2026-11-21T03:51:21+00:00 phase=7 state=open review_scope=in -->
### p7-r7 · finding [open] (reviewer: in scope) · marker comments went on waiting PRs outside the queue and never said a PR left it (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r8 created=2026-11-21T03:51:21+00:00 phase=7 state=open review_scope=in -->
### p7-r8 · finding [open] (reviewer: in scope) · the comment rebuilt its own view and could disagree with the pass line (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r9 created=2026-11-21T03:51:21+00:00 phase=7 state=open review_scope=in -->
### p7-r9 · finding [open] (reviewer: in scope) · a PR ejected then deferred was listed twice in the wave report (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r10 created=2026-11-21T03:51:21+00:00 phase=7 state=open review_scope=in -->
### p7-r10 · finding [open] (reviewer: in scope) · the queue line printed hold open for a hold read as absent (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r11 created=2026-11-21T03:51:21+00:00 phase=7 state=open review_scope=in -->
### p7-r11 · finding [open] (reviewer: in scope) · this repo's release_workflow key started two release runs per drain (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r12 created=2026-11-21T03:51:21+00:00 phase=7 state=open review_scope=in -->
### p7-r12 · finding [open] (reviewer: in scope) · board-pasted queue commands carried no --repo or --org (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r13 created=2026-11-21T03:51:21+00:00 phase=7 state=open review_scope=in -->
### p7-r13 · finding [open] (reviewer: in scope) · a failed landed comment was never retried (phase 7)

<!-- fr:journal kind=finding scope=plan id=p7-r1-resolved created=2026-11-21T03:51:21+00:00 phase=7 state=fixed resolves=p7-r1 -->
### p7-r1-resolved · finding [fixed] · resolves p7-r1: the queue marker comment trusted any author (phase 7)

the marker is taken only from a trusted author (claims.trusted_author).

<!-- fr:journal kind=finding scope=plan id=p7-r2-resolved created=2026-11-21T03:51:21+00:00 phase=7 state=fixed resolves=p7-r2 -->
### p7-r2-resolved · finding [fixed] · resolves p7-r2: requeue --wave N accepted a wave whose queue had already opened and drained (phase 7)

requeue --wave N needs N above the effective wave and a queue never opened (wave_queue_opened).

<!-- fr:journal kind=finding scope=plan id=p7-r3-resolved created=2026-11-21T03:51:21+00:00 phase=7 state=fixed resolves=p7-r3 -->
### p7-r3-resolved · finding [fixed] · resolves p7-r3: queue_retry contradicted R24 and the spec was not amended (phase 7)

spec R24, R28 and R29 state queue_retry and queue-retry --yes.

<!-- fr:journal kind=finding scope=plan id=p7-r4-resolved created=2026-11-21T03:51:21+00:00 phase=7 state=fixed resolves=p7-r4 -->
### p7-r4-resolved · finding [fixed] · resolves p7-r4: a plain requeue did not join the next queue to open, as the CLI and docs claimed (phase 7)

plain requeue joins the lowest wave whose queue has not opened, else between waves; CLI, spec, explainer and skill say so.

<!-- fr:journal kind=finding scope=plan id=p7-r5-resolved created=2026-11-21T03:51:21+00:00 phase=7 state=fixed resolves=p7-r5 -->
### p7-r5-resolved · finding [fixed] · resolves p7-r5: the wave report text selected records by the original wave and across scopes (phase 7)

_wave_report_text reads the scope's records for each member's effective wave; tested over real records.

<!-- fr:journal kind=finding scope=plan id=p7-r6-resolved created=2026-11-21T03:51:21+00:00 phase=7 state=fixed resolves=p7-r6 -->
### p7-r6-resolved · finding [fixed] · resolves p7-r6: the close-out PR body report predated the drain and omitted the close-out (phase 7)

the report lists the close-out itself; the body is not rewritten and spec and explainer say the release shows on the Batches page.

<!-- fr:journal kind=finding scope=plan id=p7-r7-resolved created=2026-11-21T03:51:21+00:00 phase=7 state=fixed resolves=p7-r7 -->
### p7-r7-resolved · finding [fixed] · resolves p7-r7: marker comments went on waiting PRs outside the queue and never said a PR left it (phase 7)

comments only on queue entries, positions count testing entries, a leaving PR is told once.

<!-- fr:journal kind=finding scope=plan id=p7-r8-resolved created=2026-11-21T03:51:21+00:00 phase=7 state=fixed resolves=p7-r8 -->
### p7-r8-resolved · finding [fixed] · resolves p7-r8: the comment rebuilt its own view and could disagree with the pass line (phase 7)

entry_comments reads plan.view.

<!-- fr:journal kind=finding scope=plan id=p7-r9-resolved created=2026-11-21T03:51:21+00:00 phase=7 state=fixed resolves=p7-r9 -->
### p7-r9-resolved · finding [fixed] · resolves p7-r9: a PR ejected then deferred was listed twice in the wave report (phase 7)

each PR is listed once, last state wins.

<!-- fr:journal kind=finding scope=plan id=p7-r10-resolved created=2026-11-21T03:51:21+00:00 phase=7 state=fixed resolves=p7-r10 -->
### p7-r10-resolved · finding [fixed] · resolves p7-r10: the queue line printed hold open for a hold read as absent (phase 7)

a hold read as absent is reported missing.

<!-- fr:journal kind=finding scope=plan id=p7-r11-resolved created=2026-11-21T03:51:21+00:00 phase=7 state=fixed resolves=p7-r11 -->
### p7-r11-resolved · finding [fixed] · resolves p7-r11: this repo's release_workflow key started two release runs per drain (phase 7)

release_workflow removed from .fr/triage.yaml with a comment.

<!-- fr:journal kind=finding scope=plan id=p7-r12-resolved created=2026-11-21T03:51:21+00:00 phase=7 state=fixed resolves=p7-r12 -->
### p7-r12-resolved · finding [fixed] · resolves p7-r12: board-pasted queue commands carried no --repo or --org (phase 7)

the board snapshot carries scope_args like the driver.

<!-- fr:journal kind=finding scope=plan id=p7-r13-resolved created=2026-11-21T03:51:21+00:00 phase=7 state=fixed resolves=p7-r13 -->
### p7-r13-resolved · finding [fixed] · resolves p7-r13: a failed landed comment was never retried (phase 7)

CommentBook retries a failed landed comment until it lands.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-21T05:47:17+00:00 -->
### lens-review-1 · review · Lens review — security, errors, tests, docs-accuracy: 27 in-scope findings fixed, 3 pre-existing

Four lens reviewers read the whole feature diff against origin/main, one per lens in the run's lens set. They raised 30 findings: 27 in scope, all fixed in b7b622cac..558b129c3, and 3 security findings that predate this change. Spec R12 and §E (approval succession), R26 and §J (postmerge marker) and Test Plan 5 were amended. Full suite after the fixes (-m ""): 17355 passed, 122 skipped, exit 0; ruff, mypy, fr docs check, fr validate artifacts, fr acceptance check and the sync checks pass.

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-security-r1 · finding [open] (reviewer: in scope) · patch-id approval was position-blind: a moved hunk kept approved-fr

<!-- fr:journal kind=finding scope=plan id=l-security-r2 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-security-r2 · finding [open] (reviewer: in scope) · a bare fr-queue:postmerge-done label lifted the DevOps barrier

<!-- fr:journal kind=finding scope=plan id=l-security-r3 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-security-r3 · finding [open] (reviewer: in scope) · the release marker matched anywhere in a body and used its own trusted-author list

<!-- fr:journal kind=finding scope=plan id=l-security-r4 created=2026-11-21T05:47:17+00:00 state=open review_scope=out -->
### l-security-r4 · finding [open] (reviewer: out of scope) · ci.yml declares no token permissions

<!-- fr:journal kind=finding scope=plan id=l-security-r5 created=2026-11-21T05:47:17+00:00 state=open review_scope=out -->
### l-security-r5 · finding [open] (reviewer: out of scope) · a push to fr-hold/** can run release.yml with the app key

<!-- fr:journal kind=finding scope=plan id=l-security-r6 created=2026-11-21T05:47:17+00:00 state=open review_scope=out -->
### l-security-r6 · finding [open] (reviewer: out of scope) · the version and relock commands run in a worktree holding PR code

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · a transport failure on the landing push read as a refusal and halted the queue

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · a hold write that failed in transport halted the queue

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-errors-r3 · finding [open] (reviewer: in scope) · a GitError mid-execute ended the drive and could lose the halt or slot-lost record

<!-- fr:journal kind=finding scope=plan id=l-errors-r4 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-errors-r4 · finding [open] (reviewer: in scope) · an unreadable patch-id voided the approval

<!-- fr:journal kind=finding scope=plan id=l-errors-r5 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-errors-r5 · finding [open] (reviewer: in scope) · an unreadable queue config told the DevOps stage to merge by hand

<!-- fr:journal kind=finding scope=plan id=l-errors-r6 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-errors-r6 · finding [open] (reviewer: in scope) · an unreadable comment list read as no markers

<!-- fr:journal kind=finding scope=plan id=l-errors-r7 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-errors-r7 · finding [open] (reviewer: in scope) · an unreadable PR read back as unmerged

<!-- fr:journal kind=finding scope=plan id=l-errors-r8 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-errors-r8 · finding [open] (reviewer: in scope) · resume read a failed merge check as not merged

<!-- fr:journal kind=finding scope=plan id=l-errors-r9 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-errors-r9 · finding [open] (reviewer: in scope) · resume failed on a recorded combination this clone never had

<!-- fr:journal kind=finding scope=plan id=l-errors-r10 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-errors-r10 · finding [open] (reviewer: in scope) · a failed queue entry write lost its cause

<!-- fr:journal kind=finding scope=plan id=l-errors-r11 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-errors-r11 · finding [open] (reviewer: in scope) · archive_moves raised without its cause

<!-- fr:journal kind=finding scope=plan id=l-errors-r12 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-errors-r12 · finding [open] (reviewer: in scope) · a queue repo whose base could not be read was skipped silently

<!-- fr:journal kind=finding scope=plan id=l-errors-r13 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-errors-r13 · finding [open] (reviewer: in scope) · clear_hold's failure did not say the release had published

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · removing the train dropped the version-conflict, relock and build-output tests

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · no real-git test of the leased push failing after main moved

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · no drive-level test of a session push voiding an approval

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · the smoke test did not pin judgements schema 13

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · fr-wave-driver.md said a waiting pr-open batch takes a slot

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · fr-wave-driver.md said a landing frees its slots in the same pass

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-docs-accuracy-r3 · finding [open] (reviewer: in scope) · fr-wave-driver.md's 'head it has only just pushed' was false

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-docs-accuracy-r4 · finding [open] (reviewer: in scope) · merge-protection.md still described the forge-queue mode and omitted the land: push bypass need

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r5 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-docs-accuracy-r5 · finding [open] (reviewer: in scope) · fr-exit-gates.md said the DevOps stage merges

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r6 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-docs-accuracy-r6 · finding [open] (reviewer: in scope) · fr-triage.md's verb list lacked defer, requeue and queue-retry

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r7 created=2026-11-21T05:47:17+00:00 state=open review_scope=in -->
### l-docs-accuracy-r7 · finding [open] (reviewer: in scope) · code strings in labels.py, queue_comment.py and drive_pass still said the DevOps stage merges

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-security-r1 -->
### l-security-r1-resolved · finding [fixed] · resolves l-security-r1: patch-id approval was position-blind: a moved hunk kept approved-fr

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-security-r2-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-security-r2 -->
### l-security-r2-resolved · finding [fixed] · resolves l-security-r2: a bare fr-queue:postmerge-done label lifted the DevOps barrier

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-security-r3 -->
### l-security-r3-resolved · finding [fixed] · resolves l-security-r3: the release marker matched anywhere in a body and used its own trusted-author list

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-security-r4-resolved created=2026-11-21T05:47:17+00:00 state=open resolves=l-security-r4 out_of_scope=true -->
### l-security-r4-resolved · finding [out-of-scope] · resolves l-security-r4: ci.yml declares no token permissions

Pre-existing: ci.yml had no permissions block before this change; the queue adds a trigger, not the token scope.

<!-- fr:journal kind=finding scope=plan id=l-security-r5-resolved created=2026-11-21T05:47:17+00:00 state=open resolves=l-security-r5 out_of_scope=true -->
### l-security-r5-resolved · finding [out-of-scope] · resolves l-security-r5: a push to fr-hold/** can run release.yml with the app key

Pre-existing exposure class: release.yml already minted the app token on push; tracked as a hardening follow-up outside this feature.

<!-- fr:journal kind=finding scope=plan id=l-security-r6-resolved created=2026-11-21T05:47:17+00:00 state=open resolves=l-security-r6 out_of_scope=true -->
### l-security-r6-resolved · finding [out-of-scope] · resolves l-security-r6: the version and relock commands run in a worktree holding PR code

Pre-existing: the old train ran the same version and relock commands in the PR checkout; this change keeps that behaviour.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: a transport failure on the landing push read as a refusal and halted the queue

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: a hold write that failed in transport halted the queue

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-errors-r3 -->
### l-errors-r3-resolved · finding [fixed] · resolves l-errors-r3: a GitError mid-execute ended the drive and could lose the halt or slot-lost record

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-errors-r4-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-errors-r4 -->
### l-errors-r4-resolved · finding [fixed] · resolves l-errors-r4: an unreadable patch-id voided the approval

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-errors-r5-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-errors-r5 -->
### l-errors-r5-resolved · finding [fixed] · resolves l-errors-r5: an unreadable queue config told the DevOps stage to merge by hand

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-errors-r6-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-errors-r6 -->
### l-errors-r6-resolved · finding [fixed] · resolves l-errors-r6: an unreadable comment list read as no markers

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-errors-r7-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-errors-r7 -->
### l-errors-r7-resolved · finding [fixed] · resolves l-errors-r7: an unreadable PR read back as unmerged

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-errors-r8-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-errors-r8 -->
### l-errors-r8-resolved · finding [fixed] · resolves l-errors-r8: resume read a failed merge check as not merged

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-errors-r9-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-errors-r9 -->
### l-errors-r9-resolved · finding [fixed] · resolves l-errors-r9: resume failed on a recorded combination this clone never had

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-errors-r10-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-errors-r10 -->
### l-errors-r10-resolved · finding [fixed] · resolves l-errors-r10: a failed queue entry write lost its cause

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-errors-r11-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-errors-r11 -->
### l-errors-r11-resolved · finding [fixed] · resolves l-errors-r11: archive_moves raised without its cause

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-errors-r12-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-errors-r12 -->
### l-errors-r12-resolved · finding [fixed] · resolves l-errors-r12: a queue repo whose base could not be read was skipped silently

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-errors-r13-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-errors-r13 -->
### l-errors-r13-resolved · finding [fixed] · resolves l-errors-r13: clear_hold's failure did not say the release had published

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: removing the train dropped the version-conflict, relock and build-output tests

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: no real-git test of the leased push failing after main moved

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: no drive-level test of a session push voiding an approval

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: the smoke test did not pin judgements schema 13

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: fr-wave-driver.md said a waiting pr-open batch takes a slot

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: fr-wave-driver.md said a landing frees its slots in the same pass

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-docs-accuracy-r3 -->
### l-docs-accuracy-r3-resolved · finding [fixed] · resolves l-docs-accuracy-r3: fr-wave-driver.md's 'head it has only just pushed' was false

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r4-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-docs-accuracy-r4 -->
### l-docs-accuracy-r4-resolved · finding [fixed] · resolves l-docs-accuracy-r4: merge-protection.md still described the forge-queue mode and omitted the land: push bypass need

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r5-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-docs-accuracy-r5 -->
### l-docs-accuracy-r5-resolved · finding [fixed] · resolves l-docs-accuracy-r5: fr-exit-gates.md said the DevOps stage merges

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r6-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-docs-accuracy-r6 -->
### l-docs-accuracy-r6-resolved · finding [fixed] · resolves l-docs-accuracy-r6: fr-triage.md's verb list lacked defer, requeue and queue-retry

Fixed in b7b622cac..558b129c3 with tests; full suite green after.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r7-resolved created=2026-11-21T05:47:17+00:00 state=fixed resolves=l-docs-accuracy-r7 -->
### l-docs-accuracy-r7-resolved · finding [fixed] · resolves l-docs-accuracy-r7: code strings in labels.py, queue_comment.py and drive_pass still said the DevOps stage merges

Fixed in b7b622cac..558b129c3 with tests; full suite green after.
