# Post-merge truth: labels, claims and archive PRs after a batch merges — design

**Date:** 2026-10-14
**Batch:** `merge-truth` (derio-net/super-fr#1190, #1172, #1161, #1160, #1176, #1178), one PR on `feat/batch-merge-truth`.
**Workflow:** `fr-goal`

## Background

After a batch's PR merges, three outward surfaces drift away from the truth, and
the driver neither repairs them nor says so.

**Labels on closed issues.** 206 closed super-fr issues still carry
`fr:in-progress` (measured live 2026-10-13). `claim_writes.release()` returns
`Done("none")` when this scope's own marker is not standing
(`packages/fr/src/fr/triage/claim_writes.py:237-238`), so a closed issue whose
claim was already released, or never existed, keeps its labels. `claim sync`
releases only own claims on **open** issues (`claim_sync.py:134-140`) plus the
members of a *releasing* batch (`claims.py:289-292`: cancelled, abandoned,
archived). For an owed member that is closed, it plans a refresh
(`claim_sync.py:121-124`). `fr triage clean-labels` is manual. It removes only
`fr:in-progress` (`triage_cmd.py:904-906`), and it skips a hit that "now carries
`fr:claimed`" (`:901`). So a closed issue whose only marker is untrusted, but
which carries `fr:claimed`, can never be cleaned.

**`release-pending` is not always true (#1161).** Collect marks a closed hit
`release-pending` whenever this scope's own claim stands on it
(`collect.py:959-960`). The page says "the next `fr triage claim sync --yes`"
clears it (`render.py:1138-1142`). For a member of a merged batch whose close-out
is not yet archived, sync plans a refresh, not a release, so the copy is false.

**`claim take` ordering (#1190.3).** `take` releases the rival's marker and
claims on the forge (`claim_writes.py:295-296`), and only then appends
`claim_taken` (`triage_claim_cmd.py:264-268`). If that write fails, the forge
keeps the claim and the judgements do not know about it. After the next collect,
`owed_releases` (`claims.py:361-364`) sees an own claim that is not owed, and
sync releases the claim it just took.

**Retire needs a manual collect (#1190.4).** `scope retire` ends with "re-run
`fr triage collect` before `claim sync`" (`triage_claim_cmd.py:397-399`).
`test_scope_retire_previews_then_releases_every_stale_claim` checks only the
release, and `tests/scenarios/triage-claims-expired.sh` never runs retire.

**Archive PRs found by head are `pending` forever (#1172).** Two paths feed the
drive's archive step (`triage_batch_cmd.py:4053-4092`):
1. Open `chore/*` PRs from `facts.prs`, with a real `checks_verdict`.
2. PRs found by the close-out head through `_live_head_prs`, which hard-codes
   `checks="pending"` (`triage_batch_cmd.py:3238`).

`facts.prs` holds only *unlinked* PRs (`collect.py:730-734`). It also holds a
paced collect's carried repo's previous list, never re-listed
(`collect.py:609-611, 735-736`). An archive PR opened after a repo's last full
read, or one that links an issue, therefore reaches the step only by path 2, and
stays `pending`. The ready filter (`batch_drive.py:1318`) requires
`OPEN and not draft and checks == "green"`. A PR that fails it only increments
`closing` (`:1332`): no action and no line. The board reads `facts.prs` alone
(`kanban.py:142-156`) and says "no archive PR" (`kanban.py:131-139`).

**Conflicting archive PRs stall for days (#1190.2).** The archive step never
reads `mergeable`. `_archive` calls `pr_merge` (`triage_batch_cmd.py:5480`), and
the forge refuses with "the merge commit cannot be cleanly created". Every later
pass prints "stopped again" (`:5486-5491`), and `record_stop` is never called, so
the board shows nothing. driver-resilience's archive PR #1146 was `CONFLICTING`
(live, 2026-10-13). Batch PRs, by contrast, have `conflict_decision`
(`batch_drive.py:569-598`), which hands the conflict to a session and raises the
`merge-conflict` Need once hand-backs are spent.

**Draft archive PRs.** An archive PR a close-out session left as a draft never
passes the ready filter. For batch PRs, draft does not decide: an approved draft
is enqueued and marked ready (`batch_drive.py:1038`). Archive PRs need no
`approved-fr`. Their gate is attribution (`attributed()`, `batch_drive.py:684-707`).
The `not p.draft` term is the only reason such a PR stalls.

**Reconciled follow-ups.**
- #1176 (`merge_ctx` aborts without `origin/HEAD`). It is mostly fixed by #1141's
  `gitseam.default_branch` fallback (`gitseam.py:451-467`). When origin cannot
  answer, `_archive` (`:5477`), `_recover` (`:5085`), the enqueue path (`:4945`),
  `_export_merge` (`:5649`) and `_hand_back` (`:5271`) still reach `merge_ctx`
  outside any guard and abort the pass. No `--yes` drive test covers either case.
- #1178 (`wait_out` renewal retrying a GraphQL read). It is resolved by #1153's
  R12: `gh.repo_visibility` (`gh.py:781-832`) is conditional REST. The 60 s retry
  (`triage_batch_cmd.py:3047-3070`) remains only for a failed REST or git renewal.
  No test pins that the renewal spends no GraphQL.
- #1160 test gaps:
  - `claim_sync` unlabelling through exactly one release edit.
  - An untrusted-author closed hit.
  - The board note, tested only as a function
    (`test_triage_clean_labels.py:77-84`).

## Requirements

R1. A closed issue needs no claim. Every `fr triage claim sync --yes` and every `fr triage batch drive --yes` pass releases this scope's own un-released claim on each closed issue in scope (owed or not, member of a running batch or not). It removes `fr:in-progress` and `fr:claimed` from that issue unless another scope's trusted, un-released claim stands on it. A batch never refreshes or re-claims a closed member.

R2. The same commands remove both labels from every closed in-scope issue labelled `fr:in-progress` or `fr:claimed` that has no trusted, un-released claim. This covers an issue whose only markers are untrusted or released, and one that never had a marker. `fr triage clean-labels --yes` acts on the same set, removes both labels, and no longer skips an issue because it carries `fr:claimed`.

R3. Collect's closed set covers closed issues labelled `fr:in-progress` or `fr:claimed`. Each label removal re-reads the issue first. It leaves the issue alone if it reopened or a foreign trusted claim appeared, and restores the labels if one appears during the edit.

R4. `release-pending` means "this scope's own claim stands on a closed issue, and the next `claim sync --yes` or `drive --yes` pass releases it and removes its labels". A closed member of a still-running batch is `release-pending`. `fr triage check`, the backlog page and the batch board say so, and nothing they say about the set is false.

R5. `fr triage claim take` records `claim_taken` in the judgements before any forge write. If that write fails, nothing is written to the forge and `take` exits non-zero. If a forge write fails after it, `take` exits non-zero, and the next `claim sync --yes` claims the member, because the recorded take owes it.

R6. `fr triage scope retire --yes` marks every claim it released as released in the stored facts. Afterwards, without a collect in between, `fr triage check` shows none of them held, and `fr triage claim sync --yes` claims the members a batch owes. Retire no longer tells the operator to run `fr triage collect`.

R7. The drive reads, from the forge, the checks of an attributed open archive PR that the facts do not hold. It applies the same verdict rules as to any archive PR, and never assumes `pending`.

R8. A paced collect never carries a repo that has a batch whose close-out has started and is not archived. Its open PRs are listed on every pass.

R9. On every pass in which an attributed open archive PR is not merged, the drive prints one line naming the batch, the PR and the reason: checks pending, checks failing, conflicting, draft being marked ready, or wrong base.

R10. The batch board's archive text covers every attributed archive PR the facts hold, linked ones included. When one exists, the card names it and what it waits on. It never says "no archive PR".

R11. Under `--yes`, the drive marks a draft attributed archive PR ready, then merges it once it is green, like any archive PR. No `approved-fr` label is involved.

R12. The drive never tries to merge an archive or export PR that the forge reports as conflicting.
- A conflicting archive PR is handed to its batch: the drive messages the batch's close-out session if it is idle, and otherwise starts a fresh close-out conflict item. The hand-back limit is the same as for batch PRs.
- Once the hand-backs are spent, it appears under Needs you now as an archive-conflict item (never as failing CI), and the stop is recorded.
- A conflicting export PR goes straight to Needs you now, because no session owns it.

R13. When the drive cannot resolve a repo's default branch, because origin cannot answer, it holds that repo's merge, archive, recover, export and hand-back work for the pass with one warning line, and the pass continues. A clone without `origin/HEAD` whose origin answers heals itself and merges.

R14. `fr triage batch drive`'s lease renewal while it waits out an exhausted GraphQL window spends no GraphQL.

R15. When the closed in-progress set is not empty, the rendered batch board carries the note naming it and the command that clears it.

## Design

### A. One closed-issue settlement (R1–R4)

**Engine.** A new pure planner, `fr.triage.claims.closed_settlements(facts, me, trusted)`, returns one target per closed hit in `facts.stale_in_progress` whose state is `stale` or `release-pending`. A `held` hit is never a target. A new writer, `claim_writes.settle_closed(client, repo, number, me, trusted)`, does the forge work:
1. Re-read the issue and its comments.
2. Stop, as `Done("none")`, if the issue reopened or a trusted, un-released foreign claim stands.
3. Rewrite this scope's own un-released marker to its released form, if one stands.
4. Remove `RELEASE_LABELS` through the existing `_remove_label`, which keeps the re-read and restore race.

This is the release that `release()` refuses to do for a closed issue with no marker. `release()` itself is unchanged.

**Callers.** `claim_sync.plan_sync` emits one `settle` op per target. For closed members it drops the `refresh` it emits today, because a closed member is never owed (R1). `claim_sync.execute` runs `settle` ops under `--yes` and records the own releases in `claims_released`, as it does today. The driver's claim phase (`_claim_plan`, `triage_batch_cmd.py:3816`) reuses `plan_sync`, so every drive pass settles closed issues for the repos it read live. A carried repo's targets wait, as its other live-read actions do (`_LIVE_READ_ACTIONS`). `clean-labels --yes` runs the same `settle_closed` over its targets. That removes its `fr:claimed` skip and its `fr:in-progress`-only removal, and it stays GitHub-only.

**Collect.** The closed-hits query (`collect.py:875-970`) widens from `fr:in-progress` to either label. Classification is unchanged: no trusted signers means `stale`, own only means `release-pending`, any foreign means `held`. `claims_of` keeps treating untrusted markers as absent, so an untrusted-only `fr:claimed` hit is `stale` and gets settled.

**Copy.** `render.py:1138-1142` and `check.py:31-35` already say "next claim sync". They add "or drive pass", and state that stale ones clear the same way, so `clean-labels` is the manual equivalent rather than the only route. The board note (`triage_kanban_cmd.py:359-367`) says the same.

### B. `claim take` records first (R5)

`triage_claim_cmd.py:214-268` reorders. Validate, append `ClaimTakenEvent` with `_write`, and only then call `cw.take`. A `TriageError` from `_write` exits 2 before any forge call. A forge failure after the write exits 2 and names the recorded take and `fr triage claim sync --yes` as the repair. Because the member is now owed through `taken_keys` (`claims.py:317`), sync claims it.

### C. Retire updates the stored facts (R6)

After `scope retire --yes` releases its claims, it rewrites `facts.json`, atomically through the existing facts writer. Each released claim's `Issue.claims` entry gets `released` set to the write time. The closing line drops the collect instruction and instead says `claim sync --yes` will claim the members. A new scenario, `tests/scenarios/triage-retire-sync.sh`, runs against a fake REST forge in the style of `fixtures/merge-train-label-gate/bin/gh`: retire, then `check` (nothing held), then `claim sync --yes` (the members claimed).

### D. Archive PRs the drive can see and finish (R7–R11)

- **Live checks (R7).** `_live_head_prs` stops hard-coding `pending`. For an OPEN PR absent from path 1, it computes the verdict with `batch_merge.live_checks` (`batch_merge.py:254-262`), the same rule path 1 uses. Path 1 also scans `issue.prs` for archive heads, so a linked archive PR gets the facts' verdict.
- **Fresh PR lists (R8).** `probe.plan_pass` (`probe.py:189-223`) never puts a repo with a batch at `closing` (close-out recorded, not archived) into `only`'s carried set.
- **Waiting lines (R9).** The archive step emits `Action("warn", batch, "archive PR #N: <reason>")` for every attributed open PR that gets no `archive` action, with one reason. `views.needs_you` stops mapping every warn to `failing-ci`: an archive warn is a status line, not a Need.
- **Board (R10).** `kanban._archive_prs` also reads linked archive PRs from `issue.prs`, and applies the trust rule `attributed()` uses. `_idle_hint` names the PR and its wait reason.
- **Drafts (R11).** The ready filter drops `not p.draft`. A draft that is otherwise ready gets an `archive` action flagged `draft`. Under `--yes`, `_archive` calls `client.pr_ready` before `pr_merge`. This is the same client call the merge train uses for approved drafts.

### E. Conflicting archive and export PRs (R12)

`_archive_prs` adds `mergeable` from `pr_view` (already read there for `base_ref`) to each attributed open PR. In the archive step, a `CONFLICTING` PR gets a new `Action("archive-conflict", …)` instead of `archive`. `_archive_conflict` in the command reuses `conflict_decision` (`batch_drive.py:569-598`) over the batch's events and the archive head:
- `skip`: an event exists for this head.
- `held`: hand-backs are spent. It writes the event, raises a new Need kind `archive-conflict` in `views.py`, and calls `record_stop` so the board shows it.
- `hand`: `_hand_back` targets the batch's close-out item (`closeout_item_id`, `batch_drive.py:498`). It messages the session if it is idle, or starts a fresh close-out conflict item whose brief names the PR and says to merge `main` into its head.

An export PR has no session. A conflicting one goes straight to `held`. `_archive` (`triage_batch_cmd.py:5486-5491`) also calls `record_stop` on a forge refusal, as `_stopped_line` does. A refusal that slipped past the `mergeable` read is then visible too.

### F. Default branch unknown (R13)

`merge_ctx` (`triage_batch_cmd.py:3490-3521`) and `_base_rules` (`:3528`) raise one typed `DefaultBranchUnknown` for both `ForgeReadError` and `GitError`. Every caller (`_archive`, `_recover`, the enqueue path, `_export_merge`, `_hand_back`) catches it, says `held: <repo> default branch unknown (<cause>)` once per pass, and skips that repo's write. The pass goes on.

### G. Tests that close #1160 and #1178 (R14, R15)

- **One release edit.** `claim_sync.execute` on a released member asserts exactly one label-removal edit.
- **Untrusted closed hit.** An untrusted-author closed hit carrying `fr:claimed` is classified `stale` and settled with both labels removed.
- **Rendered note.** A rendered `board.html` with a non-empty closed set contains the note.
- **No GraphQL in `wait_out` (#1178).** A `wait_out` test with an exhausted GraphQL window asserts the renewal's visibility read goes through `gh.repo_visibility` (REST), with no GraphQL call.
- **#1176.** Two `--yes` drive tests: a clone with no `origin/HEAD` whose origin answers merges, and an unreachable origin holds the repo and finishes the pass.

## Acceptance rows

One row per requirement group, presented at spec-review:
- `triage-closed-issues-unclaimed` (R1–R3, R15)
- `triage-release-pending-true` (R4)
- `triage-claim-take-recorded-first` (R5)
- `triage-retire-then-sync` (R6)
- `triage-archive-pr-visible` (R7–R10)
- `triage-archive-pr-draft-merged` (R11)
- `triage-archive-pr-conflict-handed` (R12)
- `triage-default-branch-unknown-held` (R13)
- `triage-waitout-no-graphql` (R14)
- `triage-post-merge-truth-live` (R1, R2, R12, post-merge)

## Verification

strategy: candidate
- triage-closed-issues-unclaimed: candidate
- triage-release-pending-true: none — a classification and copy change; unit tests render `check` and both pages from fixed facts.
- triage-claim-take-recorded-first: none — the failure needs an injected judgements-write fault; unit tests drive `claim take` against a fake client and a failing writer.
- triage-retire-then-sync: candidate
- triage-archive-pr-visible: none — needs live head lookups and check reads; unit tests drive the archive step and `_live_head_prs` against a fake client.
- triage-archive-pr-draft-merged: none — unit tests drive `_archive` against a fake client and assert `pr_ready` before `pr_merge`.
- triage-archive-pr-conflict-handed: none — the hand-back needs a runner; unit tests drive the decision, the Need and `record_stop`.
- triage-default-branch-unknown-held: none — the two `--yes` drive tests above, against git fixtures.
- triage-waitout-no-graphql: none — unit test over `wait_out` with a fake client counting GraphQL calls.
- triage-post-merge-truth-live: live — only a released `fr` driving the real super-fr scope can show that the 206 labels clear and that #1146 is handed back or listed under Needs you now.

## Test Plan

- post-merge — operator-driven: after release, run one `fr triage batch drive --yes` pass over derio-net/super-fr. Then `gh issue list --state closed --label fr:in-progress` lists only issues another scope's claim holds (today, none). Archive PR #1146 has been handed to a close-out session or is listed under Needs you now as an archive conflict, and is not reported as "stopped again".

## Non-goals

- Changing who adds `fr:in-progress` or when. Dispatch stays the only adder.
- The bridge's own `fr:in-progress` lifecycle on plan tracking issues (`item_state.py`).
- Backing off the 60 s renewal retry for a failed REST or git read (#1178 is closed as resolved by #1153).
- Archive or export PR support on GitLab or Gitea. Forge writes stay `GhClient`-only, as today.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
