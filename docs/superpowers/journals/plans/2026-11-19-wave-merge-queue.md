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
