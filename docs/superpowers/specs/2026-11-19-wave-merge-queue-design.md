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
R2. The queue is wave-exclusive. While a repo's queue is open for a wave, only that wave's batch PRs and that wave's close-out enter it. A later wave's PRs wait as PRs. The later wave's queue opens only once the previous wave's release has been cut, which the release signals by clearing the hold (R17). Some entries belong to no wave: a batch with no wave, a close-out owed once a post-merge gate passed (R15), and a DevOps housekeeping PR. Each of them forms a one-entry queue between waves, under the same hold rules.
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
R15. When the repo keeps fr's artifacts on the default branch (`placement: repo`), each wave has exactly one collected close-out. It takes every landed batch of the wave that no post-merge gate holds, and is the queue's last entry: the queue does not drain until it lands. A batch a post-merge gate holds (`gate:tester`, or `gate:devops` after its merge) is left out. Its close-out is owed once the gate passes and queues between waves (R2). A wave with no ungated landed batch has no close-out. It enters the queue under today's trust check (`review_reasons`) in place of an approval. It is landed like any entry, with no approval when that check is empty. Under `quiet` or `stealth` placement, the queue holds batch PRs only.
R16. A wave's close-out is never held by a stale artifact that a registered migration can move. The close-out migrates the artifacts it archives on its own branch before it archives them, and the close-out's trust check accepts that as part of the archive.
R17. The hold is a handshake between the driver and the repo's release. While a repo's queue is open, the driver keeps a hold ref on the repo, `refs/heads/fr-hold/<scope-id>`, in state `open`. It points at the queue's base, and its commit message names the scope, the wave, the state and the time it was opened or refreshed. The driver refreshes it each pass. When the queue drains (close-out included), the driver's last landing push moves the hold to state `drained`, at the drained `main`. The release clears it: once a release run has finished for a drained hold's commit or a later one, it deletes the hold. That holds whatever the run did: an RC, a final, or "nothing installable". An RC counts as cut. A repo with `queue.release: none` has its hold deleted by the driver at drain.
R18. `fr release status` reports a repo as held while an `open` hold exists that was refreshed within 24 hours. It names the scope and the wave. An older `open` hold is ignored, with a warning that names it. A `drained` hold never holds a release: it asks for one. super-fr's `release.py` reads the hold refs with plain git and cuts no release, RC or final, while one holds. After a run whose base contains a drained hold's commit, it deletes that hold in the same job, as its last step. The daily cron stays the backstop.
R19. When the hold moves to `drained`, the driver dispatches the repo's release workflow if `.fr/triage.yaml` names one (`queue.release_workflow`). A failed dispatch is a warning, never a failure: the next push or the daily cron releases. A `drained` hold that no release has cleared after `queue.release_wait_hours` (default 6) is a Needs-you entry. It names the hold and the command that deletes it by hand.
R20. In a repo whose services report `ci none`, a combination is green once it is built without a conflict. Such a repo's queue lands each built entry with no CI wait.
R21. `fr validate artifacts` takes a mode that accepts an artifact that is stale but movable by a registered migration, and fails only on one whose migration refuses (or that no migration reaches). This repo's CI `validate-artifacts` job uses that mode on pull requests and on `fr-queue/**` pushes.
R22. The per-merge train (`_walk_merge_train`'s merge and update path) and the forge merge-queue mode (`_walk_queue`, `enqueue`) are removed from the driver. A repo whose base branch requires a forge merge queue, or refuses the driver's push and is not set to `land: merge`, is held. The reason names the setting or permission it needs. Events already written (`update`, `enqueue`) are still read.
R23. `fr triage batch merge` merges through the same queue engine in the foreground (one repo, the named or approved batches). There is no second merge path.
R24. The queue's state is recorded as events through the one judgements writer, on the scope's state ref: queue opened, entry built (combination sha, the entry's head, its patch-id, the base), entry ejected (why), landed (the new `main`, the entries), queue drained. A restarted driver resumes from those events and the forge, never from memory, and never lands a combination twice.
R25. The driver pass, the board and the Batches page show each repo's queue in one line form. The line has the wave, the base, each entry with its state (building, testing, green, ejected, waiting, barrier), what landed and the hold's state. A PR that waits on the queue is never shown as awaiting approval once it has one.
R26. A PR that `gate:devops` holds before merge is a queue barrier. The DevOps stage runs its pre-merge ops (stage 1). Its terminal confirmation (stage 2) then releases the PR to the queue, and it no longer merges the PR itself. The queue lands that entry alone: the landed prefix ends at it, with nothing after it in the same push. The queue then lands nothing more until the DevOps stage has recorded its post-merge ops as done (stage 4). The release of the entry and the completion of the post-merge ops are both events on the scope's state, written through the one judgements writer, which the driver reads. A combination behind the barrier may be built and tested meanwhile; it lands only after the barrier lifts.
R27. A broken hold never makes the queue land untested code or touch a PR branch. A foreign push to `main` while the hold is `open` is R14. A missing or expired `open` hold while the queue is open is re-armed on the next pass. The driver reports it once, as a Needs-you entry naming the release (tag and commit) that may have cut from a partly landed wave, if one did. A release commit that lands on `main` mid-queue is a foreign move like any other.
R28. The operator hears through three channels. (a) Needs-you entries, each with a command to paste: an entry ejected with its budget spent, a held queue (R7, R22), a re-armed or uncleared hold (R19, R27), a stalled drain (R30), and a barrier waiting on the DevOps stage longer than `queue.stall_hours`. (b) One marker comment per queued PR, edited in place as its state changes: queued at position k, testing in combination <sha>, ejected (why and what to do), landed at <sha> in wave N. It honours `forge.comments: off`. (c) A wave report at drain: the landed, ejected and deferred PRs, the CI cycles, wall time and approvals per PR, and the release the drain asked for. It is written into the wave close-out PR's body and onto the Batches page.
R29. A batch can leave its wave. `fr triage batch defer <id>` takes it out of the wave's queue and its drain. It records a `deferred` event naming the wave and keeps the PR open, so its session can go on. `fr triage batch requeue <id> [--wave N]` asks for it to join a later queue: wave N's (its queue must not be open yet), or by default the next queue to open, as a between-waves entry (R2). Both verbs work through the one judgements writer and print what they changed. A deferred batch no longer holds the wave's close-out. Its own close-out is owed after it lands.
R30. The driver never takes a batch out of a wave by itself. It proposes it. When every other batch of the open wave is landed, cancelled, abandoned or deferred, and one batch still blocks the drain, the driver adds a Needs-you entry with the `defer` and `requeue` commands. That happens when the blocking batch has a spent hand-back budget, or has made no progress (no new head, no landing) for `queue.stall_hours` (default 4). A wave drains once every batch is landed, cancelled, abandoned or deferred.

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
(foreign base move, R14), `queue-hold` (refresh, or re-arm, R27), `queue-drain` (the hold
to `drained` in the last land, dispatch the release), `queue-idle` (the release
cleared the hold, or `release: none` clears it), `queue-held` (a repo that cannot
take part, R7, R22), and the Needs of R28 and R30.

### B. Choosing the wave (R2)

A repo's queue goes through three phases, each read from its events and the hold
ref:

1. **open**: from `queue-open` to `queue-drained`. The hold is `open`.
2. **releasing**: from `queue-drained` until the hold is gone. The hold is `drained`.
3. **idle**: no hold.

Only an idle repo opens a queue. It opens one for the lowest wave that has an
entry ready by R3. With none, it takes the oldest between-waves entry (R2): a
no-wave batch, a passed gate's owed close-out, a DevOps housekeeping PR, or a
requeued batch with no wave named. A later wave's ready PR is reported as waiting
on the open (or releasing) wave, and is never queued.

Entries join an open queue in readiness order. The first ready entry opens the
queue; the others need not be approved yet. The wave drains once every batch of
the wave is landed, cancelled, abandoned or deferred (R29), and its close-out
(R15), if it has one, has landed. A between-waves queue drains when its one entry
lands.

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

When the last batch entry of the open wave lands (or is deferred), the driver
starts the wave's collected close-out, as today. The difference is that its members
are the wave's landed batches that no post-merge gate holds (`is_gated` reads false),
not every owed batch of the repo. A gated batch's close-out is owed once `fr gate
pass` (or the DevOps stage's stage 6) passes it. It then queues between waves, as a
collected close-out of its own, still started by the driver. Its PR enters the queue as the
last entry once `review_reasons` is empty. The close-out verb runs `fr migrate
artifacts` restricted to the artifacts it archives, as its own commit on the
close-out branch, before `fr archive`. `archive_allowed` already accepts the
resulting deletion out of a live directory and the addition under
`docs/superpowers/implemented/`. The trust check is extended to accept the
migration commit as one of the branch's commits, and to record it. A batch landed
outside a wave's queue (before this change) keeps today's per-repo collection.

### G. Release hold, a handshake (R17–R19)

The hold is a branch, so plain git sees it on any forge, and `release.py` can read
it with `git ls-remote origin 'refs/heads/fr-hold/*'` and no credential. It is not
under `fr-queue/`, so it triggers no queue CI. Its commit message is
`fr-hold: <scope-id> wave <N> <open|drained> opened <ISO> refreshed <ISO>`.

- **open.** `release.py` passes the hold refs into `fr release status
  --from-json`, which stays credential-free. A run under a fresh `open` hold prints
  `held: wave <N> of <scope> is draining` and releases nothing.
- **drained.** The driver's last landing push of a queue moves the hold to a commit
  saying `drained` in the same atomic push. The push that moves `main` for the last
  time therefore starts a release run that is free to release.
- **cleared.** When that run (or any later one) finishes with a base that contains
  the drained hold's commit, whether by publishing, by "nothing installable", or by
  being superseded by a run that does so, it deletes the hold as its last step. In
  `release.yml` that step runs in the job that ends the run (`publish`, or `prepare`
  when it cuts nothing), with the token those jobs already hold. A failed run never
  deletes it, so a failed release keeps the next wave waiting and becomes a Needs-you
  entry after `queue.release_wait_hours`.

The driver reads "the hold is gone" as "the release is cut" and moves the repo to
idle. A consumer repo with its own release honours the same three states: it can
use `fr release status`, or delete the hold from its own release job.
`queue.release: none` means the repo has no release, and the driver deletes the hold
at drain itself.

### J. Gates (R15, R26)

`gate:devops` acts before and after the merge (`PRE_MERGE_HOLD_GATES`). The DevOps
stage (`fr ops gate`, `fr/ops/gate.py`) keeps its eight stages. Stage 2 changes:
after the operator's terminal confirmation it writes a `queue-release` event (PR,
head, patch-id) instead of calling `pr_merge`. Stage 2 is done once the PR reads
`MERGED` on the forge, which is the existing `_merged` check. Stage 4's completion
writes `queue-postmerge-done`. The planner treats a `gate:devops`-held entry as a
barrier: it enters the queue only with a `queue-release` event at its current
patch-id, it lands as the last entry of its push, and the queue lands nothing behind
it until `queue-postmerge-done`.

`gate:tester` acts only after the merge. A tester-gated batch lands like any entry.
The release that follows its wave is an RC (release gating, unchanged), which is
what the Tester walks. Its close-out queues between waves once the gate passes.

### K. A broken hold (R27)

| What happened | What the queue does |
|---|---|
| A stray merge or push moved `main` | Rebuild on the new `main` (R14), report it once, touch no PR branch |
| The hold was deleted while `open` | Re-arm it next pass; Needs-you, naming any release cut from a part-landed wave |
| The hold expired (no driver pass for 24 h) | The same on the driver's return; the release may have cut what had landed, which is a tested state |
| A release commit landed mid-queue | A foreign move: the leases make the queue's next push fail, and it rebuilds |
| A drained hold was never cleared | Needs-you after `queue.release_wait_hours`, with the deletion command |

Every land is an atomic push with leases, and every combination is tested before
it lands. A broken hold can therefore cost a rebuild and an early release, but it
never lands untested code.

### L. Keeping the operator in the loop (R28)

Problems go to Needs you, which the board and the pass output already carry. Each
new entry has a command to paste. Progress goes on the PR: one marker comment per
queued PR (`<!-- fr-queue -->`), edited in place through the `GhClient` adapter,
never a new comment per event. Success goes in the wave report: when the queue
drains, the driver renders it from the queue's events (pure, in `wave_queue`). It
writes the report into the close-out PR's body, under a section that
`review_reasons` ignores, and onto the Batches page.

### M. Leaving a wave (R29, R30)

`defer` and `requeue` are `fr triage batch` subcommands next to `edit` and
`cancel`. They write `deferred` and `requeued` events. The planner reads a deferred
batch as terminal for its wave's drain, and a requeued one as an entry of the
queue it names. Stall detection is pure: it reads the batch's last head change and
its last event from the snapshot, against `Snapshot.now`. The proposal it makes is
a Needs-you entry, never an action that writes.

### H. Validation of migratable artifacts (R21)

`fr validate artifacts --allow-migratable` treats a stale stamp with a registered
migration path as passing and prints it as `stale, migratable`. A refusing
migration, an unreachable version, or a newer-than-this-fr stamp still fails.
`ci.yml`'s `validate-artifacts` job passes the flag on `pull_request` and on
`fr-queue/**` pushes, and runs without it on `main`.

### I. What is removed (R22, R23)

`_walk_merge_train`, `_walk_queue`, `merge_ready`'s update path, `update_failing`,
the `reupdate` rule of `red_decision`, the `enqueue` action and its executor, and
the strict-checks routine-commit exemption, and the DevOps stage's own `pr_merge`
in stage 2 (§J). `batch merge` becomes "open a queue
for these batches and drive it in the foreground until it drains or stops".

### Config (`.fr/triage.yaml`)

```yaml
queue:
  ci: push            # required: the repo's CI runs on fr-queue/** pushes
  depth: 2            # combinations in CI at once
  land: push          # push | merge
  release: workflow   # workflow | none (none: the driver clears its own hold)
  release_workflow: release.yml   # optional: dispatched when the hold is drained
  release_wait_hours: 6           # a drained hold not cleared by then is a Need
  stall_hours: 4      # a batch blocking the drain this long is proposed for deferral
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
18. Wave sequencing: wave N drains, the hold reads `drained`; wave N+1's approved green PRs stay waiting; the release run deletes the hold (once each for an RC, a final, and "nothing installable"); the next pass opens wave N+1's queue. A failed release run leaves the hold, and after `release_wait_hours` it is a Need. (R2, R17, R18, R19)
19. Gates: a `gate:devops` PR enters only after `queue-release`, lands alone, and nothing lands behind it until `queue-postmerge-done`; a combination behind it is tested meanwhile. A `gate:tester` batch lands, is left out of the wave close-out, and its own close-out queues between waves after `fr gate pass`. (R15, R26)
20. Broken hold: a deleted `open` hold is re-armed with one Need; an expired one the same; a release commit landing mid-queue fails the next lease and the queue rebuilds; no case lands an untested tree or moves a PR branch. (R27)
21. Channels: each Need of R28 appears with its command; the PR marker comment is edited in place through queued, testing, ejected and landed (and is absent under `forge.comments: off`); the wave report lists landed, ejected and deferred PRs with their cycles and approvals. (R28)
22. Leaving: `defer` takes a batch out of the drain, so the wave drains and its close-out leaves it out; `requeue --wave N+1` puts it in N+1's queue; `requeue` alone makes it a between-waves entry; a stall past `stall_hours`, or a spent budget, gives one Need with both commands and never an automatic deferral. (R29, R30)
23. Post-merge, live: the next wave on this repo drains through the queue; record the number of PR updates (expected 0), CI cycles per PR, approvals per PR (expected 1), and releases cut (expected 1 for the wave). (all; row `wave-queue-live-wave`)
