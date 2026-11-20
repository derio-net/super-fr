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
