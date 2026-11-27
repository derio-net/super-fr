# Queue follow-ups: approval revive, conflict probe, close-out wait, repo-name case

Batch `queue-followups` of derio-net/super-fr: super-fr#1680, #1676, #1663, #1695, one PR.

## Background

Four small defects of the wave merge queue (spec `2026-11-19-wave-merge-queue`) and its driver:

- **#1680.** `fr.triage.approval._live_index` (`packages/fr/src/fr/triage/approval.py:138`)
  takes the last `ApprovalEvent` of a PR with no `voided_at` as live. Only fr's own void
  (`settle_approvals`, `:301`; `settle_entry_approval`, `:367`) records `voided_at`, so a label
  removed by anyone else leaves the old approval live. A later `approved-fr` is then judged
  against the old head's patch-id and voided at once (PR #1630, 2026-11-24). The approval that
  started it was recorded at a conflicting head. And fr removes the label without saying why
  on the PR.
- **#1676.** `fr.triage.batch_merge.trial_conflicts` (`batch_merge.py:257`), the early conflict
  probe (`triage_batch_cmd.py:6442`), reports every path `unresolvable` leaves. The queue's
  own build (`queue_exec._resolve`, `queue_exec.py:257`) also resolves `reviewed:` stamp
  hunks, generated-block hunks and whole generated paths through `regen.classify_conflicts`
  (`regen.py:162`). So a conflict the queue would resolve still costs a hand-back when the PR
  is outside a queue slot.
- **#1663.** `fr.triage.batch_drive.closeout_due` (`batch_drive.py:744`) is due on a release
  commit or after `CLOSEOUT_FALLBACK` (10 min, `:85`). Under the queue, the hold
  `fr-hold/queue` keeps any release from being cut until the drain, which waits for the
  close-out. So every queued wave waits the full fallback. Because the rule is judged per
  batch, wave 23 got two collected close-outs. And a quiet paced pass (`probe.pass_kind`,
  `probe.py:162`) never notices that the fallback has elapsed.
- **#1695.** `fr.triage.plan_overlap.overlaps` (`plan_overlap.py:195`) compares `a.repo != b.repo`
  exactly, so two spellings of one repo never overlap.

## Requirements

R1. When a settling pass reads a PR's labels and `approved-fr` is absent while an approval of that PR is live, fr records the approval as ended. The record is one `ApprovalEvent` whose `head` is the approved head and whose `voided_at` is the live head, in the existing judgements schema (14). A later label is then a `First` at the live head. Unread labels (`None`) and a pass that does not settle end nothing. This holds for batch PRs (`settle_approvals`) and for non-batch queue entries (`settle_entry_approval`). The drive output says `approval of PR #<n> at <head> ended: label removed`. An ended approval is not a label fr removed: it changes no facts and posts no comment.
R2. A batch PR that carries `approved-fr` and has no live approval is `Waiting`, a new verdict, and its approval is not recorded, while both of these hold: the forge reads its live head as conflicting (`fr.triage.mergeability.conflicting`), and a `ConflictEvent` recorded by the conflict probe names that head (the probe found a conflict the queue cannot resolve). `Waiting` keeps the label, records nothing, and does not make the PR a queue member. Its readiness fact reads `approved, waits for a conflict-free head`. The board asks no one to label it. The drive says so once per head, not as a warning. The first settling pass at which either condition fails records the approval at the live head (`First`), so a repaired conflict needs no second approval. A conflict the queue resolves (no `ConflictEvent` at the head), an `UNKNOWN` mergeability, and a non-batch entry are recorded as today. The trade-off: a label read in the window before GitHub computes mergeability, or before the probe ran at that head, is still recorded at a conflicting head. A live approval's verdict is unchanged: the R12 void rules of `2026-11-19-wave-merge-queue` stay.
R3. Every removal of `approved-fr` by fr posts one new PR comment that names the reason and the fix, for example `approval voided: its diff changed at <sha>; review the new head and label it approved-fr again`. The comment carries the marker `<!-- fr-queue:approval-voided head=<voided head> -->`. It is posted at most once per voided head: a marker comment for that head by a trusted author already on the PR suppresses it. Nothing is posted when the repo's `forge.comments` is off or its policy cannot be read. A comment that fails to post is a warning and never undoes the void.
R4. `trial_conflicts` sorts the paths `unresolvable` leaves with `regen.classify_conflicts`, using the repo's `generated:` globs and treating the default branch's side as the combination's side. It returns the paths the queue's classification refuses for a merge of the PR onto the default branch: the real ones, plus the whole-generated and regenerate ones when the repo declares no `mirrors:`. It does not model a rebase-method replay, a merge onto an earlier entry, or a mirrors run that fails. The probe writes nothing the repo keeps, as before.
R5. A landed batch that a `queue_land` record of its repo names is due at once: its close-out waits for no release and no fallback. The same `due` value also gates the repo's `post_merge` action, and that is intended: the hold blocks a release until the drain anyway, and the queue's landing normally runs `post_merge` itself (`post_merge` is then not owed). A batch merged outside the queue keeps the release-or-`CLOSEOUT_FALLBACK` rule. The pass (`drive_pass`) and the command's due list (`triage_batch_cmd`) read the one rule through `wave_queue.queue_landed`.
R6. A wave's collected close-out starts only when no ungated landed member of that wave and repo that has no close-out yet is still not due, unverified (`snap.unverified`) or ledger-unread (`snap.ledger_unknown`). It then takes every due member. While a wave waits, the pass emits one `held` action that names the members it waits for and why, as the `post_merge` wait does. A member held by the verb (`closeout_hold`) or not selected does not hold the wave.
R7. A paced pass that would be quiet reads a repo when a close-out deadline of that repo passed since the last planned pass. A deadline is `merged_at + CLOSEOUT_FALLBACK` of a landed batch that no `queue_land` names and that has no close-out event. Pacing fails open: an unknown last-pass time, or a landed batch with no readable `merged_at`, reads its repo. `PacingState` records the last planned pass's time as `planned_at`. A missing or unparseable `planned_at` is unknown and leaves the rest of `pacing.json` as it is.
R8. `overlaps` compares repository names case-insensitively.

## Design

### Approval (R1–R3), `fr/triage/approval.py`

- `Waiting(head, why)` joins `ApprovalVerdict`, and `is_approved` stays false for it.
  `approval_verdict` takes `waits: bool = False`. With the label on, no live approval and
  `waits`, it returns `Waiting(head, "waits for a conflict-free head")` instead of
  `First(head)`. `judge_approval` passes `waits` through. `settle_approvals` computes it
  from the live `pr_view`'s `mergeable`/`merge_state` and the batch's `ConflictEvent`s:
  `conflicting(...)` and a `ConflictEvent` with `head == live head`.
  `settle_entry_approval` always passes `False`.
- Ended (R1): when `labels is not None`, the label is absent and `_live_approval(...)` is
  not `None`, both settle functions write `ApprovalEvent(head=<approved>,
  voided_at=<live head>, patch_id=<carried>)` (under `dry_run` they say `would end`),
  return `Unlabelled`, and call no forge write. In `_settle_approvals`
  (`triage_batch_cmd.py:5595`) the `voided` set (labels fr removed, used to rewrite
  `facts.json`) gains only events written after a label removal. The writer is told which
  kind it got, for example by a separate `record` callback or a returned set of removed
  PRs, so an ended approval is not counted.
- Board and readiness (R1, R2): `readiness._approval_fact` gives `Waiting` the line
  `approved, waits for a conflict-free head`. `views.needs_you` skips a `Waiting` PR for
  `approve-pr`: its conflict Need already speaks for it. For an ended approval the
  re-label Need keeps its wording only when `voided_at != approved head`, because a push
  moved the head. When `voided_at == approved head`, it says `PR #n: approval ended (label
  removed): label it approved-fr to merge`. The `voided by a push` readiness fact follows
  the same split.
- `_comments_off(client, repo)` sits beside `_labels_off` (`approval.py:597`): it reads
  `client_policy(client, repo).block("comments")`, and an unreadable policy blocks.
  `operator_entries._comments_off` becomes a re-export of it, since `operator_entries`
  already imports `approval`. `void_comment(client, repo, number, head, why, say)` is called
  right after each `edit_issue_labels(... remove=APPROVED_FR)`. It returns early when
  comments are off, or when a trusted marker for `head` is in `list_issue_comments`
  (`_trusted_markers`). Otherwise it calls `comment_pr`. Any exception goes to `say` as a
  warning.

### Conflict probe (R4), `fr/triage/batch_merge.py`

`trial_conflicts` takes `generated: Sequence[str] = ()` and `mirrors: bool = False`. After
`merge_main`, it runs `classify_conflicts` over the refused paths, reading each path's text
from the scratch worktree and its stages with 2 and 3 swapped (in the probe "ours" is the PR
head; the combination's side is main's). It returns `real + (whole + regenerate if not
mirrors else [])`. The call site (`triage_batch_cmd.py:6442`) passes
`facts.config_for(repo).generated` and `bool(...mirrors)`. `WorktreeSeam` gains
`unmerged_stages` and `read`; `gitseam.Worktree` has both (`:1408`, `:1313`).

### Close-out due (R5–R7)

- `batch_drive.closeout_due(*, released, merged_at, now, queued=False)`: `queued` is due
  at once. `drive_pass` passes
  `batch.id in queue_landed(r for r in snap.queue_records if r.repo == repo)`, and the
  command's due list (`triage_batch_cmd.py:4640`) passes the same over `judgements.queues`.
- The collecting loop records, per `(repo, wave)`, the members that block it: not due,
  unverified, or ledger-unread, each among ungated landed members with no close-out. At the
  start step a blocked key emits `Action("held", <first>, "the wave's close-out waits for
  <ids>: <why>")` and starts nothing.
- `probe.deadline_repos(facts, judgements, since, now)` returns the repos of landed batches
  that no `queue_land` names, that have no close-out event, and whose
  `merged_at + CLOSEOUT_FALLBACK` lies in `(since, now]`. A batch whose `since` is `None` or
  whose `merged_at` is missing is included whenever it is landed. `Pacer.plan`
  (`pacing.py:127`) passes them to `plan_pass` together with the `closing` repos.
  `pacing_state` gains `planned_at` and adds it to `_TIMES`. `load` parses it on its own,
  so a bad value is `None` rather than a reset of the whole state. The planned-pass save in
  `pacing.py` stamps it.

### Overlap (R8), `fr/triage/plan_overlap.py`

`a.repo.lower() != b.repo.lower()`.

## Design shape

```text
packages/fr/src/fr/triage/
  approval.py        + Waiting verdict; approval_verdict(+waits)                                 R2
                     ~ settle_approvals / settle_entry_approval: label gone + live -> end it    R1
                     + _comments_off(), void_comment(): one marked PR comment per voided head   R3
  operator_entries.py ~ _comments_off re-exported from approval                                 R3
  readiness.py       ~ approval fact: Waiting; ended vs push-voided                           R1 R2
  views.py           ~ approve-pr Need: skip Waiting; ended wording                           R1 R2
  batch_merge.py     ~ trial_conflicts(+generated, +mirrors) -> regen.classify_conflicts         R4
  batch_drive.py     ~ closeout_due(+queued)                                                     R5
                     ~ collected close-out held (with a `held` action) for blocking members      R6
  probe.py           + deadline_repos(); plan_pass reads them like closing repos                 R7
  pacing.py          ~ plan() passes deadline repos; planned-pass save stamps planned_at         R7
  pacing_state.py    + planned_at in PacingState and _TIMES, parsed fail-open                   R7
  plan_overlap.py    ~ overlaps(): repo compared lower-cased                                     R8
packages/fr/src/fr/commands/triage_batch_cmd.py
                     ~ due list passes queued; probe passes generated/mirrors;          R1 R4 R5
                       voided set counts only fr's removals
```

## Verification

strategy: none
- queue-approval-label-lifecycle: none — unit tests of `approval_verdict`, both settle functions, the readiness fact and the approve-pr Need over a fake client, in this PR's CI
- conflict-probe-matches-queue-resolution: none — a trial-merge unit test over a real scratch git repo, in this PR's CI
- queue-closeout-due-at-landing: none — `drive_pass`, `closeout_due` and pacer unit tests over built snapshots, in this PR's CI
- wave-overlap-repo-case: none — an `overlaps` unit test, in this PR's CI
gate: developer
settle.conflicts: report — batch queue-followups: the wave driver owns this PR's mergeability
settle.ci: report — batch queue-followups: the wave driver owns this PR's CI

One acceptance row per issue, as decided: `queue-approval-label-lifecycle` covers R1–R3
(#1680), and the row first drafted for R2 alone is retired into it. No Test Plan: nothing here
needs a released build to show.

## Out of scope

- An approval already recorded and then voided by a hand-resolved conflict repair keeps
  R12's rule (l-security-r1 of the wave-merge-queue spec): its patch-id changed, so the
  operator approves again. R2 covers only an approval that was never recorded.
