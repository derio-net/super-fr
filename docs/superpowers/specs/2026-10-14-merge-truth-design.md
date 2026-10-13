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

R1. A closed issue needs no claim. Every `fr triage claim sync --yes` and every `fr triage batch drive --yes` pass releases this scope's own un-released claim on each closed in-scope issue (owed or not, member of a running batch or not). It removes `fr:in-progress` and `fr:claimed` from that issue unless another scope's trusted, un-released claim stands on it. A batch never refreshes or re-claims a member that the facts show closed. A member the facts do not hold (unviewed, or its repo skipped) keeps today's due-only refresh.

R2. The same commands remove both labels from every closed in-scope issue labelled `fr:in-progress` or `fr:claimed` that has no trusted, un-released claim (the `stale` entries). This covers an issue whose only markers are untrusted or released, and one that never had a marker. `fr triage clean-labels --yes` stays the manual route for the `stale` entries only, as today. It now removes both labels, and no longer skips an issue because it carries `fr:claimed`.

R3. Collect's closed set covers closed issues labelled `fr:in-progress` or `fr:claimed`. Each label removal re-reads the issue first. It leaves the issue alone if it reopened or a foreign trusted claim appeared, and restores the labels if one appears during the edit.

R4. `release-pending` means "this scope's own claim stands on a closed issue, and the next `claim sync --yes` or `drive --yes` pass releases it and removes its labels". A closed member of a still-running batch is `release-pending`. `fr triage check`, the backlog page and the batch board say so, and nothing they say about the set is false.

R5. `fr triage claim take` records `claim_taken` in the judgements before any forge write.
- If that write fails, nothing is written to the forge and `take` exits non-zero.
- If the forge refuses the take (the holder refreshed since the facts, or a claim stands), `take` withdraws the event it just recorded and exits non-zero. No take is recorded for a take that did not happen.
- If a forge write fails for any other reason, `take` exits non-zero and leaves the event recorded. The next `claim sync --yes` claims the member, because the recorded take owes it.

R6. `fr triage scope retire --yes` removes every claim it released from the stored facts. Afterwards, without a collect in between, `fr triage check` shows none of them held, and `fr triage claim sync --yes` claims the members a batch owes. Retire no longer tells the operator to run `fr triage collect`.

R7. The drive reads, from the forge, the checks of an attributed open archive PR that the facts do not hold. It applies the same verdict rules as to any archive PR, and never assumes `pending`.

R8. Every drive pass, of whatever kind, reads the repos of the batches whose close-out has started and is not archived, so their open PRs are current.

R9. On every pass, each attributed open archive PR the drive does not merge gets exactly one line naming the batch, the PR and why:
- checks pending or failing: a waiting line;
- conflicting: the conflict line (R12);
- wrong base: the existing blocked line.
A draft the drive is merging gets that merge's own line, which says it was marked ready.

R10. The batch board's archive text covers every attributed archive PR the facts hold, linked ones included. When one exists, the card names it and what it waits on. It never says "no archive PR".

R11. Under `--yes`, the drive marks a draft attributed archive PR ready, then merges it once it is green, like any archive PR. No `approved-fr` label is involved.

R12. The drive never tries to merge an archive or export PR that the forge reports as conflicting.
- A conflicting archive PR is handed to its batch's close-out:
  - If the close-out session is idle, the drive messages it.
  - If it is working or blocked, nothing is sent, and the drive retries on the next pass.
  - If it is absent or done, the drive starts a fresh archive-conflict session.
  - At most two hand-backs are made per close-out. After that, the PR appears under Needs you now as an archive conflict (never as failing CI), and the stop is recorded.
- A conflicting export PR goes straight to Needs you now with a recorded stop, because no session owns it.
- A recorded stop clears when that PR merges.

R13. When the drive cannot resolve a repo's default branch, because origin cannot answer, it holds that repo's merge, archive, recover, export and hand-back work for the pass with one warning line, and the pass continues. A clone without `origin/HEAD` whose origin answers heals itself and merges. Every other forge read failure behaves as today.

R14. `fr triage batch drive`'s lease renewal while it waits out an exhausted GraphQL window spends no GraphQL.

R15. When the closed set holds `stale` or `release-pending` entries, the rendered batch board carries a note naming them. It says the next `claim sync --yes` or drive pass clears them, and names `clean-labels --yes` as the manual route for the stale ones.

## Design

### A. One closed-issue settlement (R1–R4, R15)

**Collect.** The closed-hits read (`collect.py:902-970`) makes two closed `list_issues` reads per repo, one per label, because gh ANDs repeated `--label` flags (`gh.py:268`). The results are deduplicated by number, and each read warns on truncation. Classification is unchanged:
- no trusted signers → `stale`;
- own only → `release-pending`;
- any foreign → `held`.

`read_claims` (`claims.py:190`) keeps treating untrusted markers as absent, so an untrusted-only `fr:claimed` hit is `stale`. The `StaleInProgress` docstring and the copy that name `fr:in-progress` alone name both labels.

**Engine.** A new pure planner, `claims.closed_settlements(facts)`, returns one target per closed hit whose state is `stale` or `release-pending`. A `held` hit is never a target. A new writer, `claim_writes.settle_closed(client, repo, number, me, trusted)`, does the forge work:
1. Re-read the issue and its comments.
2. Stop, as `Done("none")`, if the issue reopened or a trusted, un-released foreign claim stands.
3. Rewrite this scope's own un-released marker to its released form, if one stands.
4. Remove `RELEASE_LABELS` through the existing `_remove_label`, which keeps the re-read and restore race.

`release()` itself is unchanged.

**Sync ops.** `claim_sync.OpKind` gains `settle`.
- `ClaimOp.batch` becomes optional: a settle op carries the batch only when the key is a member of one of this scope's batches. Every other op kind still requires it.
- `plan_sync` emits one `settle` op per target.
- For an owed member that the facts show closed, `plan_sync` drops the refresh it plans today. `issue is None` keeps the due-only refresh (R1).
- `execute` runs settle ops under `--yes`.
- `released()` and `record_releases` count a settle op that released an own marker on a member, so `claims_released` is recorded as for a release.

**Driver.**
- `_claim_plan` (`triage_batch_cmd.py:3816-3852`) maps settle ops to a new `Snapshot.settles_owed`.
- `drive_pass` emits them as a new `Action("settle", …)` after the releases.
- The carried-repo filter for a settle op uses the repo of the issue key, not `repos.get(op.batch)`.
- `kanban.py`'s phrase map gains `settle`.

**`clean-labels`.** It keeps its target predicate (`clean_label_targets`, the `stale` entries; `check.py:389-393`) and runs `settle_closed` over them. That drops its `fr:claimed` skip (`triage_cmd.py:901`) and its `fr:in-progress`-only removal. It stays GitHub-only. The existing row `triage-closed-in-progress-set` and its scenario `tests/scenarios/triage-closed-in-progress.sh` keep their target set. The row's notes and unit level move to "both labels".

**Copy.** These name the next `claim sync --yes` or drive pass as what clears `stale` and `release-pending` entries, and `clean-labels --yes` as the manual route for `stale` ones:
- `render.py:1138-1142`
- `check.py:31-35`
- the board note `in_progress_note` (`triage_kanban_cmd.py:359-367`), which fires when either state is present (R15).

### B. `claim take` records first (R5)

`triage_claim_cmd.py:214-268` reorders:
1. Validate.
2. Append `ClaimTakenEvent` with `_write`. A `TriageError` here exits 2 before any forge call.
3. Call `cw.take`.

There are two kinds of forge failure after step 2:
- **Refusal.** `ClaimError` from `may_displace` (the holder refreshed) or a `Held` result means the rival still holds the issue. A second judgements write removes the event step 2 appended. It is the last event of that batch, written by this command under the same scope lock. The command then exits 2, naming the holder. If the withdrawal write fails too, it exits 2 naming the stray event.
- **Transport failure.** The command keeps the event, exits 2, and names `fr triage claim sync --yes` as the repair. The member is owed through `taken_keys` (`claims.py:299-302`), so sync claims it.

### C. Retire updates the stored facts (R6)

After `scope retire --yes` releases its claims, it removes the retired signer's entries from each affected `Issue.claims`. Facts record only un-released claims (`claims.py:213-225`), so this is what a fresh collect would write. It writes `facts.json` back in the scope's state directory through `fr.artifacts.atomic.write_text_atomic`, with no schema change. Publication to a state ref, where the scope has one, follows whatever path collect's own write takes; the plan names it. The closing line drops the collect instruction and says `claim sync --yes` will claim the members.

### D. Archive PRs the drive can see and finish (R7–R11)

- **Live checks (R7).** `batch_merge.live_checks` (`batch_merge.py:254-262`) is split. A new `pr_checks_verdict(client, repo, number, *, ci_none)` holds the rule, and the `MergeContext` form delegates to it. `_live_head_prs` calls `pr_checks_verdict` for an OPEN PR absent from path 1, instead of hard-coding `pending`. Path 1 also scans `issue.prs` for archive heads, so a linked archive PR gets the facts' verdict.
- **Fresh PR lists (R8).** `probe.plan_pass` gains `closing: set[str]`, the repos of batches with a close-out event and no archive. The caller in `pacing.py` computes it from the judgements. `plan_pass` adds `closing` to `only` on partial and essential passes. A would-be quiet pass with a non-empty `closing` becomes a partial pass that reads only `closing`. `live_repos` includes `closing`. The cost is one repo read per pass per unarchived close-out. It ends when the archive lands, and a stuck one is surfaced under R12.
- **Lines (R9).** The archive step emits `Action("warn", batch, "archive PR #N: checks <pending|failing>")` for an attributed open PR that gets no `archive`, `archive-conflict` or `blocked` action. `views.needs_you` stops mapping every warn to `failing-ci`: a warn whose text starts `archive PR` is a status line, never a Need.
- **Board (R10).** `kanban._archive_prs` also reads linked archive PRs from `issue.prs`, and applies the trust rule `attributed()` uses. `_idle_hint` names the PR and its wait reason.
- **Drafts (R11).** The ready filter (`batch_drive.py:1318`) drops `not p.draft`. A draft that is otherwise ready gets an `archive` action with `draft=True`. Under `--yes`, `_archive` calls `client.pr_ready` before `pr_merge`, the same call the merge train makes for approved drafts, and its line says "marked ready, merged".

### E. Conflicting archive and export PRs (R12)

**Detection.** `_archive_prs` already calls `pr_view` for `base_ref` (`triage_batch_cmd.py:4088`). It keeps `mergeable` from that read on each attributed open archive PR. The export step's PR read does the same for the export PR. In the archive step, a `CONFLICTING` archive PR gets `Action("archive-conflict", batch, …, pr=…, head=…)`, never `archive`.

**Event and counter.** The event is a new judgements event, kind `archive_conflict`. A batch-PR `ConflictEvent` needs refused paths (`model.py:741-756`, `min_length=1`) and shares the batch PR's hand-back counter. An archive conflict has neither, and must not raise the batch's `merge-conflict` Need.
- **Fields.** `ArchiveConflictEvent{kind: "archive_conflict", at, head, pr, delivered: session|fresh|held, handle}`.
- **Schema.** `JUDGEMENTS_SCHEMA` 9 → 10. fr reads 1–10 and writes 10, with the read-shim and fixture regeneration every judgements bump carries.
- **Decision.** `archive_conflict_decision(events, head)` in `batch_drive.py` is pure:
  - `skip`: an `archive_conflict` event exists for this head.
  - `held`: two non-held `archive_conflict` hand-backs exist since the batch's close-out event.
  - else `handback`.

**Hand-back.** `_hand_back_archive` in the command targets the close-out, never the batch items.
- Close-out item idle: message it with a brief naming the PR and its head, telling it to merge the default branch into the head and push.
- Working or blocked: nothing is sent; retried next pass.
- Absent or done: start `archive_conflict_item_id(repo, batch, n)` = `<repo>/run/archive-conflict-<batch>-<n>` through the batch's runner, with the same brief.

`held` writes the event and calls `record_stop(target, batch, MergeStop(head, "archive PR #N conflicts"))`. `views.needs_you` raises a new Need kind `archive-conflict` from a held `archive_conflict` event whose head is still the archive PR's head.

**Export.** A conflicting export PR raises the same Need kind with `record_stop` keyed `export:<repo>`. A merged archive or export PR calls `clear_stop` on its key. `_archive` (`triage_batch_cmd.py:5486-5491`) also calls `record_stop` on a forge refusal, as `_stopped_line` does.

### F. Default branch unknown (R13)

A new `DefaultBranchUnknown(ForgeReadError)` is raised only by the fetch and `checkout.default_branch()` inside `merge_ctx` (`triage_batch_cmd.py:3490-3521`) and `_base_rules` (`:3528`), where `GitError` is caught too. Every caller catches that type alone: `_archive`, `_recover`, the enqueue path, `_export_merge` and `_hand_back`. Each says `held: <repo> default branch unknown (<cause>)` once per pass and skips that repo's write. Every other `ForgeReadError` (a merge-methods or config read) behaves as today (gh#921).

### G. Tests that close #1160 and #1178 (R14, R15)

- **One release edit.** `claim_sync.execute` releasing a member asserts exactly one label-removal edit.
- **Untrusted closed hit.** An untrusted-author closed hit carrying only `fr:claimed` is collected, classified `stale`, and settled with both labels removed.
- **Rendered note.** A rendered `board.html` with a non-empty settle set contains the note.
- **No GraphQL in `wait_out` (#1178).** A `wait_out` test with an exhausted GraphQL window asserts the renewal's visibility read goes through `gh.repo_visibility` (REST), with no GraphQL call.
- **#1176.** Two `--yes` drive tests: a clone with no `origin/HEAD` whose origin answers merges, and an unreachable origin holds the repo and finishes the pass.
- **Scenarios.** Two scenarios against a fake REST forge, in the style of `tests/scenarios/fixtures/merge-train-label-gate/bin/gh`:
  - `tests/scenarios/triage-closed-settle.sh`: two closed issues, one with an own marker and one untrusted-only carrying `fr:claimed`; `claim sync --yes` removes both labels from both.
  - `tests/scenarios/triage-retire-sync.sh`: retire, then `check` (nothing held), then `claim sync --yes` (members claimed).

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

The existing row `triage-closed-in-progress-set` moves too: same target set, both labels removed (§A).

## Verification

strategy: candidate
- triage-closed-issues-unclaimed: candidate
- triage-release-pending-true: none — a classification and copy change; unit tests render `check` and both pages from fixed facts.
- triage-claim-take-recorded-first: none — the failures need injected faults; unit tests drive `claim take` against a fake client with a failing writer, a refusing forge and a failing forge.
- triage-retire-then-sync: candidate
- triage-archive-pr-visible: none — needs live head lookups and check reads; unit tests drive the archive step, `_live_head_prs` and `plan_pass` against a fake client.
- triage-archive-pr-draft-merged: none — unit tests drive `_archive` against a fake client and assert `pr_ready` before `pr_merge`.
- triage-archive-pr-conflict-handed: none — the hand-back needs a runner; unit tests drive the decision, the event, the Need, `record_stop` and `clear_stop`.
- triage-default-branch-unknown-held: none — the two `--yes` drive tests above, against git fixtures.
- triage-waitout-no-graphql: none — unit test over `wait_out` with a fake client counting GraphQL calls.
- triage-post-merge-truth-live: live — only a released `fr` driving the real super-fr scope can show that the 206 labels clear and that #1146 is handed back or listed under Needs you now.

## Test Plan

- post-merge — operator-driven: after release, run one `fr triage batch drive --yes` pass over derio-net/super-fr. Then `gh issue list --state closed --label fr:in-progress` and `gh issue list --state closed --label fr:claimed` list only issues another scope's claim holds (today, none). Archive PR #1146 has been handed to a close-out session or is listed under Needs you now as an archive conflict, and is not reported as "stopped again".

## Non-goals

- Changing who adds `fr:in-progress` or when. Dispatch stays the only adder.
- The bridge's own `fr:in-progress` lifecycle on plan tracking issues (`item_state.py`).
- Backing off the 60 s renewal retry for a failed REST or git read (#1178 is closed as resolved by #1153).
- Archive or export PR support on GitLab or Gitea. Forge writes stay `GhClient`-only, as today.
- Re-numbering the judgements schema if another PR claims 10 first: the later merge renumbers, as with facts schemas.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-14-merge-truth | `derio-net/super-fr` | `2026-10-14-merge-truth` | — |
