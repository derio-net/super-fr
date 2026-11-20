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
