# Wave merge queue — a forge-independent merge queue the wave driver owns

Issue: derio-net/super-fr#1576. Related: #1577 (overlap at planning), #1569, #1497,
#1496 (close-out holds and re-recording), #1492, #1493 (red and conflicting drafts).

## Background

On 2026-11-19 (waves 21–23) the wave driver's merge train ran the same cycle for
hours. It updated a PR that was behind, waited for full CI, lost `approved-fr`,
re-labelled, met a stale artifact or a conflict, handed back, and waited again.
Every merge restarted that cycle for every PR behind it. The measured causes (#1576):

1. **Main moves two or three times per merge.** `release.yml` runs on every push to
   `main`, so each batch merge is followed by a release commit, and each close-out
   merge moves `main` again. The train brings every PR behind `main` up to date:
   `batch_merge._update` (`packages/fr/src/fr/triage/batch_merge.py:625`) merges
   `origin/<default>` into the PR in a scratch worktree and pushes the PR's head ref
   (`:672`). Every update is a new head, a full CI cycle (14 shards, even for an
   archive-only close-out) and a fresh chance to conflict. The PRs are updated one
   after another. `_behind_only_routinely` (`:385`) spares release and archive
   commits, but only when the base does not require strict up-to-date checks, and
   only when they touch no path the PR changed.
2. **Approval is pinned to a head SHA.** `approval.approval_verdict`
   (`packages/fr/src/fr/triage/approval.py:59`) keeps an approval only while
   `reaches()` (`:78`) can chain fr's own recorded `update` events from the approved
   head to the live one. Any other push voids it and removes the label (`:140`): a
   session's merge of `main`, or an empty "re-run checks" commit (#1567), although
   neither changed what the operator approved.
3. **Live run cursors sit on `main` between the feature merge and the close-out.**
   When a shape change lands, they read as stale until the next release migrates
   them, and `validate-artifacts` fails every other PR (#1564).
4. **Two merges per feature** (the feature PR, then its close-out PR) multiply all
   of the above.

What exists today (read end to end per AGENTS.md's bridge audit rule):

- `fr.triage.batch_drive.drive_pass` is pure. It walks one **train per repo**, in
  `_dispatch_key` order (wave, then order, then id; `batch_drive.py:1473`). Waves
  are only a sort key; nothing in merging is wave-exclusive. `_walk_merge_train`
  (`:1610`) emits a `merge` action for each approved, green member.
  `triage_batch_cmd._merge_batch` executes it through `merge_ready`, one PR at a
  time; an `updated` or `pending` outcome, or a moved head, stops the train for the
  pass (`_stops_train`).
- A second mode, `_walk_queue` (`:1509`, merge-train-safety §D), hands PRs to
  GitHub's own merge queue (`pr_enqueue`, `EnqueueEvent`). It needs GraphQL, which
  the cloud driver cannot use (`queue_rest` holds it), and no other forge has an
  equivalent.
- The collected close-out (exit-gates R15) collects per **repo**, not per wave. It
  is started as a session that runs `fr triage batch closeout … --yes`. The driver
  merges its PR without approval only when `review_reasons` (`batch_drive.py:1057`)
  is empty.
- `scripts/release.py` (this repo's own release, not shipped by fr) runs on every
  push to `main`, cuts an RC or a final, and is **superseded** when `main` moves
  under it. It asks `fr release status --from-json` what waits, with no credential.
- `GhClient` already has `commit_checks(repo, sha)` (checks on a commit with no PR)
  and `dispatch_workflow`.

All three supported forges (GitHub, GitLab, Gitea) mark a PR **merged** when a
push makes its head commit reachable from the base branch. This is the property
the design lands on, because it needs no forge's merge queue and no merge API.

## Requirements

R1. The wave driver merges batch PRs through one merge queue per repo that the driver itself owns. It never uses a forge's merge queue (GitHub's, GitLab's merge trains, or any other), and never needs GraphQL.
R2. The queue is wave-exclusive. While a repo's queue is open for a wave, only that wave's batch PRs and that wave's close-out enter it. Batch PRs of a later wave wait until the queue has drained. A batch with no wave forms a one-batch queue of its own, taken between waves.
R3. A PR enters the queue only when it is open, carries a valid approval (R12), and its own head's checks are green by the existing R4 rule (`checks_verdict`). Queue order is the wave's dispatch order (`_dispatch_key`).
R4. For each queue entry, the driver builds a speculative combination: the base the queue started from (`main`), then every entry ahead of it, then this entry. Each one is a commit on an fr-owned branch `fr-queue/<scope-id>/<n>`, which the driver pushes. A PR's branch is never touched because `main` moved.
R5. The combination is built in the repo's merge method. For `merge`, one `--no-ff` merge commit per entry, with the subject `Merge pull request #<n> from <head-ref>`. For `squash`, one commit per entry holding that PR's whole change on top of the previous entry, with the subject `<PR title> (#<n>)`. For `rebase`, the PR's commits replayed onto the previous entry.
R6. Building a combination resolves conflicts only as the train does today: a declared version file whose PR change is the version alone, and a lockfile when `relock` is declared. In a repo with a `version:` block, the commit that lands an entry carries that entry's reserved version slot. Any other conflict is a real conflict, handed back to the PR's session through the existing conflict decision (`conflict_decision`, hand-back budget included). The PR leaves the queue until its head moves.
R7. The repo's CI runs on pushes to `fr-queue/**`. The repo's triage config declares this (`.fr/triage.yaml` `queue.ci: push`). The driver refuses to open a queue for a repo that does not declare it, saying what to add. The driver reads a combination's checks with `commit_checks` on the combination's own sha, applying the same required-checks rule as for a PR.
R8. At most `queue.depth` combinations are in CI at once per repo (default 2, set in `.fr/triage.yaml`). The combinations are entries 1..k from the front of the queue, so each one depends only on the entries ahead of it.
R9. When the combinations for entries 1..k are green, the driver lands the longest green prefix: `main` moves to exactly the tested commit of the last green entry. No untested tree reaches `main`.
R10. Landing by push (`queue.land: push`, the default) is one `git push --atomic` with a compare-and-swap lease on every ref it moves. In it, each landed PR's head branch moves to its own commit in the combination: under `squash` and `rebase` the PR's commit there; under `merge` its head is unchanged. `main` fast-forwards to the combination's tip. The lease on each PR branch is the head the combination was built from, and the lease on `main` is the queue's base. A server without atomic push support gets the same refs in that order: the PR heads first, then `main`. A lease that fails lands nothing new, and the queue is rebuilt on the next pass.
R11. Landing by forge merge (`queue.land: merge`, per repo) merges each landed PR through the forge's merge API, at its pinned head, in queue order, with the repo's method. The driver then checks that `main`'s tree equals the tested combination's tree. On a mismatch, or a refusal (for example a rule that requires PRs to be up to date), the queue stops and says why. It never retries in a way that lands an untested tree.
R12. Approval is pinned to content. When `approved-fr` is recorded, the driver records the PR's patch-id: `git patch-id --stable` over the diff from the merge base with the default branch to the head. The approval stays valid while the live head's patch-id equals the recorded one. A merge of `main`, an empty commit, or the driver's own rewrite at landing (R10) keeps it. A change to the PR's own diff voids it (the label is removed and the void recorded, as today). An approval recorded before this change, with no patch-id, is read by today's `reaches()` rule.
R13. A combination that fails CI, while every combination ahead of it is green, takes its entry out of the queue. The driver rebuilds that combination once as a fresh commit with the same inputs before it treats the failure as the entry's own. A second failure is handed to the PR's session through the existing red decision (`red_decision`'s hand-back, wait and needs-you rules, and its budget), with the combination's sha and its failing check names. Only the combinations behind the ejected entry are rebuilt.
R14. A move of `main` the queue did not make (a person merging another PR, or a release that ran despite the hold) never updates a PR branch. The driver rebuilds every combination on the new `main`, reports the foreign move once per new base, and keeps every approval valid by R12.
R15. When the repo keeps fr's artifacts on the default branch (`placement: repo`), each wave has exactly one collected close-out. It takes every landed batch of the wave and is the queue's last entry: the queue does not close until it lands. It enters the queue under today's trust check (`review_reasons`) in place of an approval. It is landed like any entry, with no approval when that check is empty. Under `quiet` or `stealth` placement, the queue holds batch PRs only.
R16. A wave's close-out is never held by a stale artifact that a registered migration can move. The close-out migrates the artifacts it archives on its own branch before it archives them, and the close-out's trust check accepts that as part of the archive.
R17. While a repo's queue is open, the driver keeps a hold ref on the repo, `refs/heads/fr-hold/<scope-id>`. It points at the queue's base, and its commit message names the scope, the wave and the time it was opened or refreshed. The driver refreshes the hold each pass and deletes it when the queue drains, the close-out included.
R18. `fr release status` reports a repo as held while a hold ref exists that was refreshed within 24 hours. It names the scope and the wave. An older hold is ignored, with a warning that names it. super-fr's `release.py` reads the hold refs with plain git and cuts no release, RC or final, while one holds. The daily cron stays the backstop.
R19. When the driver deletes the hold, it dispatches the repo's release workflow if `.fr/triage.yaml` names one (`queue.release_workflow`). A failed dispatch is a warning, never a failure: the next push or the daily cron releases.
R20. In a repo whose services report `ci none`, a combination is green once it is built without a conflict. Such a repo's queue lands each built entry with no CI wait.
R21. `fr validate artifacts` takes a mode that accepts an artifact that is stale but movable by a registered migration, and fails only on one whose migration refuses (or that no migration reaches). This repo's CI `validate-artifacts` job uses that mode on pull requests and on `fr-queue/**` pushes.
R22. The per-merge train (`_walk_merge_train`'s merge and update path) and the forge merge-queue mode (`_walk_queue`, `enqueue`) are removed from the driver. A repo whose base branch requires a forge merge queue, or refuses the driver's push and is not set to `land: merge`, is held. The reason names the setting or permission it needs. Events already written (`update`, `enqueue`) are still read.
R23. `fr triage batch merge` merges through the same queue engine in the foreground (one repo, the named or approved batches). There is no second merge path.
R24. The queue's state is recorded as events through the one judgements writer, on the scope's state ref: queue opened, entry built (combination sha, the entry's head, its patch-id, the base), entry ejected (why), landed (the new `main`, the entries), queue drained. A restarted driver resumes from those events and the forge, never from memory, and never lands a combination twice.
R25. The driver pass, the board and the Batches page show each repo's queue in one line form. The line has the wave, the base, each entry with its state (building, testing, green, ejected, waiting), what landed and the hold. A PR that waits on the queue is never shown as awaiting approval once it has one.

## Design

### A. Where the queue lives

The queue is a new pure planner, `fr.triage.wave_queue`, beside `batch_drive`. It
replaces `_walk_train`'s two branches (R22). `drive_pass` calls it per repo with
the snapshot and gets back actions and a `Queue` view (for `train_line`'s successor,
R25). Like `batch_drive`, it reads no clock and runs no git and no forge.

Its inputs, added to `Snapshot` by the command layer:

- the queue events for the repo (R24), from judgements;
- each queue entry's combination sha and its `commit_checks` verdict;
- `main`'s sha now (`bases`, already read for queue mode), and each PR's live head
  and patch-id;
- the repo's `queue:` config (R7, R8, R10, R11, R19) and whether the hold ref
  exists.

Its actions: `queue-open`, `queue-build` (entries i..k on base b), `queue-land`
(prefix 1..j at sha s), `queue-eject` (entry, why: conflict | red), `queue-rebuild`
(foreign base move, R14), `queue-hold` (refresh), `queue-drain` (delete the hold,
dispatch the release), and `queue-held` (a repo that cannot take part, R7, R22).

### B. Choosing the wave (R2)

The open wave of a repo is the wave recorded by its `queue-open` event that has no
`queue-drained` event. With none open, the planner opens one for the lowest wave
that has an entry ready by R3, taking a no-wave batch only when no waved batch of
the repo is in flight. A later wave's ready PR is reported as waiting for the open
wave, never queued. The wave stays open until every batch of the wave is landed,
cancelled or abandoned, and its close-out (R15) has landed. If the wave has no
close-out, it closes when the last batch lands.

### C. Building and testing (R4–R8, R13)

The command layer executes `queue-build` in a scratch worktree under the state
directory (as `_update` does today, through `gitseam`). For each entry it applies
the method's step from R5 on top of the previous entry's commit, with R6's conflict
rules and version slot. It pushes the tip to `fr-queue/<scope-id>/<wave>-<n>` and
records `entry built` for each entry. All entries 1..depth are built from one base
in one worktree, so entry k's commit is the parent of entry k+1's. CI then runs on
each pushed branch (R7). The driver keeps one branch per in-flight entry, so each
entry's sha has its own check run.

A combination that fails CI is rebuilt once with a new commit timestamp (the same
tree, a new sha, so CI runs again; R13 covers flakes). After a second failure the
entry is ejected. Every entry behind it is rebuilt on the last green entry ahead of
it. The ejected PR goes through `red_decision`. Its session gets the combination's
sha and failing checks, and the brief says the failure was seen only in combination.
A conflict during a build ejects the entry through `conflict_decision`.

### D. Landing (R9–R11)

`queue-land` lands the longest green prefix. Under `land: push`, the command issues
one `git push --atomic --force-with-lease=<ref>:<expected> …` covering:

- `refs/heads/<pr-head-ref>` → the entry's own commit, for each landed entry under
  `squash`/`rebase` (under `merge` the PR head is unchanged and already an ancestor);
- `refs/heads/<default>` → the last green entry's commit (a fast-forward).

Because each PR's head is then reachable from `main`, every forge marks it merged,
and fr's existing readers keep working unchanged. The batch PR reads `MERGED`, its
`Closes` lines close their issues, the gate labels sit on the merged PR, and
`release.py`'s first-parent PR scan finds `(#n)` or `Merge pull request #n`.
Rewriting the PR branch happens only at landing, after approval and green CI, and
only with a lease on the head the combination was built from. A session that pushed
since makes the lease fail, which lands nothing; the pass rebuilds. Under R12 the
approval survives the rewrite, because the patch-id is unchanged.

Under `land: merge` (R11), the command calls `pr_merge(head_sha=…)` per entry in
order, then compares `git rev-parse <default>^{tree}` with the combination's tree.
The driver identity needs push rights on `main` only under `land: push`. A refusal
(protection) is reported as `queue-held` naming the bypass actor, or
`queue.land: merge`.

### E. Approval by content (R12)

`ApprovalEvent` gains an optional `patch_id`. Judgements schema 13 adds it and the
queue events; fr reads schemas 1–13 and writes 13. `approval_verdict` takes the live
patch-id (computed by the command through `gitseam`). The verdict is `Approved` when
the recorded event has a patch-id and the live one equals it, and `Void` when they
differ. With no recorded patch-id, the verdict falls back to `reaches()`. Recording
(`settle_approvals`) computes the patch-id at the head it records.

A patch-id can change when `main` changes the context lines around the PR's hunks.
That voids the approval, the conservative side. It is a real change of what the
operator saw, and this design accepts it.

### F. Close-out per wave (R15, R16)

When the last batch entry of the open wave lands, the driver starts the wave's
collected close-out, as today. The difference is that its members are the wave's
landed batches, not every owed batch of the repo. Its PR enters the queue as the
last entry once `review_reasons` is empty. The close-out verb runs `fr migrate
artifacts` restricted to the artifacts it archives, as its own commit on the
close-out branch, before `fr archive`. `archive_allowed` already accepts the
resulting deletion out of a live directory and the addition under
`docs/superpowers/implemented/`. The trust check is extended to accept the
migration commit as one of the branch's commits, and to record it. A batch landed
outside a wave's queue (before this change) keeps today's per-repo collection.

### G. Release hold (R17–R19)

The hold is a branch, so plain git sees it on any forge, and `release.py` can read
it with `git ls-remote origin 'refs/heads/fr-hold/*'` and no credential. It is not
under `fr-queue/`, so it triggers no queue CI. Its commit message is
`fr-hold: <scope-id> wave <N> opened <ISO> refreshed <ISO>`. `release.py` passes
the hold refs into `fr release status --from-json`, and the gate stays
credential-free there. A held run prints `held: wave <N> of <scope> is draining`
and releases nothing. The driver's final landing push of a queue also deletes the
hold (`:refs/heads/fr-hold/<scope-id>`) in the same atomic push, so the push that
moves `main` for the last time already finds no hold. `queue.release_workflow`
then dispatches anyway, for repos whose release has no push trigger.

### H. Validation of migratable artifacts (R21)

`fr validate artifacts --allow-migratable` treats a stale stamp with a registered
migration path as passing and prints it as `stale, migratable`. A refusing
migration, an unreachable version, or a newer-than-this-fr stamp still fails.
`ci.yml`'s `validate-artifacts` job passes the flag on `pull_request` and on
`fr-queue/**` pushes, and runs without it on `main`.

### I. What is removed (R22, R23)

`_walk_merge_train`, `_walk_queue`, `merge_ready`'s update path, `update_failing`,
the `reupdate` rule of `red_decision`, the `enqueue` action and its executor, and
the strict-checks routine-commit exemption. `batch merge` becomes "open a queue
for these batches and drive it in the foreground until it drains or stops".

### Config (`.fr/triage.yaml`)

```yaml
queue:
  ci: push            # required: the repo's CI runs on fr-queue/** pushes
  depth: 2            # combinations in CI at once
  land: push          # push | merge
  release_workflow: release.yml   # optional: dispatched when the queue drains
```

This repo's own config gains the block, its `ci.yml` gains `push: branches:
['fr-queue/**']`, and `.github/ci-budget.yaml` needs no new entry (no new workflow
file). Its `merge_method: squash` keeps: R5's squash chain lands squash-shaped
history.

## Out of scope

- Flagging wave batches whose plans overlap, before they conflict (#1577).
- Red CI and conflicts on unapproved drafts (#1492, #1493). The queue takes only
  approved PRs, so those gaps stay as they are.
- #1569's second half (a retry on a held close-out branch read as reopened) and
  #1496/#1497's re-recording and approval of close-out PRs. A wave close-out held
  by `review_reasons` stays held as today.
- Cheaper CI per cycle (#1555, #1340).
- Skipping `main`'s own CI run after a fast-forward of an already tested commit.

## Verification

strategy: candidate
- wave-queue-live-wave: live — only a real wave on this repo exercises GitHub's merged-by-push detection, the atomic push against the real ruleset, and `release.yml` reading the hold; every other row is proven pre-merge by the fake forge over real bare git repositories.

gate: wave-queue-live-wave=tester

## Test Plan

1. Fake forge plus a real bare git remote: a wave of three approved green PRs; depth 2. One pass builds main+a and main+a+b on `fr-queue/…`; no PR branch moves; once both are green, one atomic push lands them and `main` equals the tested tip. (R1, R4, R8, R9, R10)
2. The same wave under `squash`: after landing, each PR's head is its squashed commit, every commit's subject is `<title> (#n)`, and the fake forge, reading reachability, reports all three merged. Under `merge` the subjects are `Merge pull request #n …`. (R5, R10)
3. Lease failure: a session pushes to b between build and land; the atomic push lands nothing; the next pass rebuilds. (R10)
4. `land: merge`: per-PR merges at pinned heads; a forced tree mismatch stops the queue with a reason. (R11)
5. Approval by content: approved at H; the session merges `main` (same patch-id) and the approval holds; an empty commit holds it; an edit to a PR line voids it and removes the label; an old event with no patch-id follows `reaches()`. (R12)
6. Red combination: main+a+b fails twice while main+a is green; a lands, b is ejected and handed back with the combination sha; c is rebuilt on main+a; one failure then a green rebuild ejects nothing. (R13)
7. Conflict during a build is handed back through `conflict_decision`; a version-file-only conflict is resolved and carries the slot. (R6)
8. Foreign push to `main`: every combination is rebuilt on the new base, no PR branch moves, the approvals hold, and the move is reported once. (R14)
9. Wave exclusivity: an approved green PR of wave N+1 waits while wave N's queue is open; a no-wave batch waits for an open wave. (R2, R3)
10. Close-out as last entry: the queue stays open until the close-out lands; the close-out takes only the wave's batches; a stale-but-migratable cursor is migrated on the close-out branch and passes `review_reasons`. (R15, R16)
11. Hold: the ref exists from open to drain; the final landing push deletes it atomically; `fr release status --from-json` with a fresh hold says held, with one older than 24 h warns and ignores it; `release.py` cuts nothing while held; the release workflow is dispatched on drain, and a failed dispatch only warns. (R17, R18, R19)
12. `ci none` repo lands each built entry with no CI wait. (R20)
13. `fr validate artifacts --allow-migratable` passes a stale movable stamp and fails a refusing one; `ci.yml` uses it on PRs and on `fr-queue/**`. (R21)
14. A repo requiring a forge merge queue, or refusing the push under `land: push`, is held with a reason; a repo with no `queue.ci` is refused with what to add; no `enqueue` or `update` event is written anywhere. (R7, R22)
15. `fr triage batch merge` drives the same engine to drain. (R23)
16. A driver killed after `entry built` and after the land push resumes from events and the forge without landing twice. (R24)
17. The pass line, the board and the Batches page show the queue line; a queued, approved PR is never "awaiting approval". (R25)
18. Post-merge, live: the next wave on this repo drains through the queue; record the number of PR updates (expected 0), CI cycles per PR, approvals per PR (expected 1), and releases cut (expected 1 for the wave). (all; row `wave-queue-live-wave`)
