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
   archive-only close-out) and a fresh chance to conflict. `_behind_only_routinely`
   (`:385`) spares release and archive commits, but only when the base does not
   require strict up-to-date checks, and only when they touch no path the PR changed.
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

- `fr.triage.batch_drive.drive_pass` (`batch_drive.py:1738`) is pure. It walks one
  **train per repo**, in `_dispatch_key` order (wave, then order, then id; `:1473`).
  Waves are only a sort key; nothing in merging is wave-exclusive.
  `_walk_merge_train` (`:1610`) emits a `merge` action for each approved, green
  member. `triage_batch_cmd._merge_batch` (`triage_batch_cmd.py:5933`) executes it
  through `merge_ready`, one PR at a time; an `updated` or `pending` outcome, or a
  moved head, stops the train for the pass (`_stops_train`, `:3775`).
- A second mode, `_walk_queue` (`batch_drive.py:1509`, merge-train-safety §D),
  hands PRs to GitHub's own merge queue (`pr_enqueue`, `EnqueueEvent`). It needs
  GraphQL, which the cloud driver cannot use (`queue_rest` holds it).
- The driver merges three more kinds of PR through `pr_merge`: per-batch archive PRs
  and collected close-out PRs (`_archive`, `triage_batch_cmd.py:6794-6807`) and the
  per-wave state-export PR (`_export_merge`, `:7099-7111`).
- `post_merge` (`.fr/triage.yaml`) runs once per merged batch, before its close-out,
  from the base clone fast-forwarded to `main` (`_post_merge`, `:6472-6508`).
- The DevOps stage (`fr ops gate`, `fr/ops/gate.py:1146`) merges a `gate:devops` PR
  itself in stage 2 (`:737-779`, `pr_merge` at `:771`). Its `_merged` check
  (`:1136`) accepts either a recorded stage 2 or a forge `MERGED`.
- Triage state (`judgements.yaml`, schema 12, `model.py:98-99`) is not an artifact
  kind (`fr.artifacts.registry` has none), so artifact-versioning does not apply. Its
  events live on `Batch`; `Judgements` holds batches, features, exports and
  closeouts (`model.py:1209-1220`).
- `scripts/release.py` (this repo's own release, not shipped by fr) runs on every
  push to `main` and daily, cuts an RC or a final, and is **superseded** when `main`
  moves under it (`:1015`). It asks `fr release status --from-json` what waits, with
  no credential (`release_cmd.py:183`).
- `GhClient` has `commit_checks(repo, sha)` (`ghclient.py:345`),
  `required_check_names` (`:356`) and `dispatch_workflow` (`:440`). The glab and tea
  clients raise `UnsupportedForgeOperation` for these and for `pr_view`, `pr_merge`
  and comment edits (`ghclient.py:556-663`, gh#611): the batch engine runs on
  GitHub (GraphQL or REST) only.

GitHub and GitLab mark a PR **merged** when a push makes its head commit reachable
from the base branch. Gitea does so only when the repo enables "autodetect manual
merge". This is the property the design lands on: it needs no forge's merge queue and
no merge API.

## Requirements

R1. The wave driver merges every PR it merges through one merge queue per repo that the driver itself owns. It never uses a forge's merge queue (GitHub's, GitLab's merge trains, or any other) and never needs GraphQL. The design uses only git and the forge operations listed in R35.
R2. The queue is wave-exclusive. While a repo's queue is open for a wave, only that wave's batch PRs and that wave's close-out enter it. A later wave's PRs wait as PRs. The later wave's queue opens only once the previous wave's release has been cut, which the release signals by clearing the hold (R17). Some entries belong to no wave (R32): a batch with no wave, a close-out owed once a post-merge gate passed (R15), a DevOps housekeeping PR, a per-wave export PR and a legacy per-batch archive PR. Each of them forms a one-entry queue between waves, under the same hold rules. The wave a repo opens next is the lowest wave that has a batch not yet terminal (landed, cancelled, abandoned or deferred). It is not the lowest wave with a ready entry, so wave N+1 never opens before wave N.
R3. A batch PR enters the queue only when it is open, carries a valid approval (R12), and its own head's checks are green by the existing R4 rule (`checks_verdict`). A non-batch entry enters under its own trust rule instead of an approval (R32). Queue order is the order in which entries became ready.
R4. For each queue entry, the driver builds a speculative combination: the base the queue started from (`main`), then every entry ahead of it, then this entry. Each is pushed to one of a bounded set of fr-owned branches, `fr-queue/<scope-id>/slot-<k>`, k from 1 to `queue.depth`. A slot is reused by a force-push leased on the sha it last held, so the branches never pile up and none is ever deleted. A PR's branch is never touched because `main` moved.
R5. The combination is built in the repo's merge method. For `merge`, one `--no-ff` merge commit per entry, with the subject `Merge pull request #<n> from <head-ref>`. For `squash`, one commit per entry holding that PR's whole change on top of the previous entry, with the subject `<PR title> (#<n>)`. For `rebase`, the PR's commits replayed onto the previous entry.
R6. Building a combination resolves conflicts only as the train does today: a declared version file whose PR change is the version alone, and a lockfile when `relock` is declared. In a repo with a `version:` block, the commit that lands an entry carries that entry's reserved version slot. Any other conflict is a real conflict, handed back to the PR's session through the existing conflict decision (`conflict_decision`, hand-back budget included). The PR leaves the queue until its head moves.
R7. Every check that gates the default branch must run on the combination. The repo declares in `.fr/triage.yaml` that it does (`queue.ci: push`): every workflow that reports a required check (the base's `required_check_names`, or `.fr/ci.yaml`'s `gate_checks`) runs on pushes to `fr-queue/**`. A repo whose services report `ci none` declares `queue.ci: none` instead. The driver refuses to open a queue for a repo with neither, saying what to add. It reads a combination's checks with `commit_checks` on the combination's own sha, under the same required-checks rule as a PR. A required check that has not reported within `queue.check_wait_minutes` (default 60) is a Needs-you entry naming the workflow that does not run on `fr-queue/**`.
R8. At most `queue.depth` combinations are in CI at once per repo (default 2). They are entries 1..k from the front of the queue, so each depends only on the entries ahead of it.
R9. When the combinations for entries 1..k are green, the driver lands the longest green prefix: `main` moves to exactly the tested commit of the last green entry. No untested tree reaches `main`.
R10. Landing by push (`queue.land: push`, the default) is one `git push --atomic`. It moves `main` by fast-forward to the combination's tip, leased on the queue's base. It also covers every landed PR's head ref, leased on the head the combination was built from. Under `squash` and `rebase` the head ref moves to the PR's own commit in the combination. Under `merge` it is pushed unchanged, so a session push since the build still fails the lease. A lease that fails lands nothing, and the queue is rebuilt on the next pass. A server that refuses `--atomic` is held (R22): there is no non-atomic fallback, because a partial push would leave PR branches holding other PRs' changes.
R11. Landing by forge merge (`queue.land: merge`, per repo) merges each landed PR through the forge's merge API, at its pinned head, in queue order, with the repo's method. The driver then checks that `main`'s tree equals the tested combination's tree. On a mismatch, or a refusal (for example a rule that requires PRs to be up to date), the queue stops and says why. It never retries in a way that lands an untested tree.
R12. Approval is pinned to content. When `approved-fr` is recorded, the driver records the PR's patch-id: `git -c diff.noprefix=false -c diff.mnemonicPrefix=false -c diff.relative=false -c diff.suppressBlankEmpty=false -c core.quotePath=true diff --binary --full-index --no-color --no-ext-diff --no-textconv --no-renames --diff-algorithm=myers --unified=3 --inter-hunk-context=0 --indent-heuristic --src-prefix=a/ --dst-prefix=b/ --no-relative --ignore-submodules=none --submodule=short -O/dev/null <merge-base> <head> | git -c patchid.stable=false -c patchid.verbatim=true patch-id --verbatim`, with `GIT_DIFF_OPTS=--unified=3`, where `<merge-base>` is the merge base of the head with the default branch (`gitseam.PATCH_ID_DIFF`, `PATCH_ID`). Every setting that shapes the diff is pinned, so no host's configuration (a textconv driver, an external diff, prefixes, renames, context or algorithm) moves the id. Whitespace and binary content therefore count. The approval stays valid while the live head's patch-id equals one fr recorded since the approval: the approval's own, or the one each of fr's own updates of the PR branch records for its new head (an `update` event's `patch_id`). A merge of `main` with no conflict resolution, and an empty commit, keep it, after an fr update too. Any other change to the PR's own diff voids it, whitespace-only and binary edits included (the label is removed and the void recorded, as today), with one known limit: `git patch-id` ignores hunk line numbers, so a change that moves an otherwise identical hunk (same lines, same context) to another position within a file keeps the id, and the approval. Before a mismatch voids, the driver fetches the default branch and reads the id once more, so a copy of `main` older than the one the PR merged never voids an approval. The patch-id is read only while the PR is open and before it lands. A landed PR is merged, and its approval is never read again. An approval recorded with no patch-id (before this change, or when the id could not be read) is read by today's `reaches()` rule until a pass reads the id while the approval still holds; the driver then records the approval again with the id, and this rule applies from then on.
R13. A combination that fails CI while every combination ahead of it is green takes its entry out of the queue. Before treating the failure as the entry's own, the driver rebuilds that combination once, as a fresh commit with the same tree. A second failure is handed to the PR's session through the existing red decision (`red_decision`'s hand-back, wait and needs-you rules, and its budget), with the combination's sha and its failing check names. Only the combinations behind the ejected entry are rebuilt.
R14. A move of `main` the queue did not make (a person merging another PR, or a release that ran despite the hold) never updates a PR branch. The driver rebuilds every combination on the new `main`, reports the foreign move once per new base, and keeps every approval valid by R12.
R15. When the repo keeps fr's artifacts on the default branch (`placement: repo`), each wave has exactly one collected close-out. It takes every landed batch of the wave that no post-merge gate holds, and is the queue's last entry: the queue does not drain until it lands. A batch a post-merge gate holds (`gate:tester`, or `gate:devops` after its merge) is left out. Its close-out is owed once the gate passes and queues between waves (R2). A wave with no ungated landed batch has no close-out. It enters the queue under today's trust check (`review_reasons`) in place of an approval, and is landed like any entry. Under `quiet` or `stealth` placement, the queue holds batch PRs only.
R16. A wave's close-out is never held by a stale artifact that a registered migration can move. Before archiving, the close-out runs `fr migrate artifacts --yes --path <p>…` over exactly the artifacts it archives, as its own commit on the close-out branch. `--path` is a new repeatable option. It migrates only the named files, and it refuses a migration that is not per-file (a retiring hop) rather than run it partly. The close-out's trust check accepts that commit as part of the archive.
R17. The hold is a handshake between the driver and the repo's release, through one ref per repo, `refs/heads/fr-hold/queue`. A hold is a commit whose message reads `fr-hold: <state> scope <scope-id> wave <N|-> opened <ISO> refreshed <ISO>`.
 - `open`: the commit's parent is the queue's base. The driver creates it at queue open with a lease that expects the ref absent or `cleared`, and refreshes it each pass.
 - `drained`: after the queue's last landing (or a drain by deferral, R29), the driver pushes the hold, leased, to a commit whose parent is the drained `main`.
 - `cleared`: the release clears the hold once it has finished a run whose base contains the drained hold's parent, whether it cut an RC, a final, or "nothing installable". An RC counts as cut. It clears the hold by deleting the ref or by pushing a `cleared` commit; a driver that cannot delete branches (the cloud proxy) only ever pushes. A repo with `queue.release: none` has its hold cleared by the driver at drain.
R18. `fr release status` reports a repo as held while its hold is `open` and was refreshed within 24 hours. It names the scope and the wave. An older `open` hold is ignored, with a warning that names it. `drained` and `cleared` holds never hold a release. super-fr's `release.py` fetches the hold ref with plain git, reads the commit message (`git ls-remote` gives only the sha), and cuts nothing, RC or final, while the hold is `open`. A `workflow_dispatch` run with `--version` is held too, and prints how to clear the hold by hand. A superseded run clears nothing; the run that supersedes it does. The run that clears a hold does so as its last step, in the job that ends the run. A failed run never clears it. The daily cron stays the backstop.
R19. Every drain reaches a release through the push of the `drained` hold. super-fr's `release.yml` runs on pushes to `fr-hold/**` that are not deletions, so a drain by landing, by forge merge or by deferral starts a release run the same way. When `.fr/triage.yaml` names `queue.release_workflow`, the driver also dispatches it. A failed dispatch is a warning. A `drained` hold that no release has cleared after `queue.release_wait_hours` (default 6) is a Needs-you entry naming the hold and the command that clears it by hand.
R20. In a repo with `queue.ci: none`, a combination is green once it is built without a conflict. Its queue lands each built entry with no CI wait.
R21. `fr validate artifacts` takes `--allow-migratable`, which accepts an artifact that is stale but movable by a registered migration. It fails only on one whose migration refuses, that no migration reaches, or that is newer than this `fr`. This repo's CI `validate-artifacts` job uses it on pull requests and on `fr-queue/**` pushes.
R22. The per-merge train (`_walk_merge_train`'s merge and update path) and the forge merge-queue mode (`_walk_queue`, `enqueue`) are removed from the driver. A repo whose base branch requires a forge merge queue, whose server refuses `--atomic`, or which refuses the driver's push and is not set to `land: merge`, is held. The reason names the setting or permission it needs. Events already written (`update`, `enqueue`) are still read.
R23. `fr triage batch merge` merges through the same queue engine in the foreground (one repo, the named or approved batches). With R32 there is no second merge path in the driver.
R24. The queue's state lives in judgements schema 13, in a new `queues:` list: one record per queue, holding its repo, wave (or none), scope, base and an ordered list of events, written through the one judgements writer on the scope's state ref. The snake_case event kinds are `queue_open`, `queue_built` (slot, combination sha, entry, its head, its patch-id, the base), `queue_eject` (entry, conflict | red | operator), `queue_land` (new `main`, entries), `queue_drain`, `queue_cleared`, `queue_release` and `queue_postmerge_done` (R26), and `approval` for a non-batch entry. A batch's own `deferred` and `requeued` events (R29) and its `ApprovalEvent` patch-id stay on the batch. An entry names a batch id, or a PR number and kind (closeout, export, archive, housekeeping) for the rest. fr reads schemas 1–13 and writes 13, and each new kind is registered in `_EVENT_SCHEMAS`. A restarted driver resumes from these events and the forge, never from memory, and never lands a combination twice.
R25. The driver pass, the board and the Batches page show each repo's queue in one line form. The line has the wave, the base, each entry with its state (building, testing, green, ejected, waiting, barrier), what landed and the hold's state. A PR that waits on the queue is never shown as awaiting approval once it has one.
R26. A PR that `gate:devops` holds before merge is a queue barrier. The DevOps stage runs its pre-merge ops (stage 1). Its terminal confirmation (stage 2) then adds the label `fr-queue:release` to the PR; it never calls `pr_merge` and records no stage 2. On its next pass the driver records `queue_release` at the PR's head and patch-id, which is how the label is settled, as with `approved-fr`. The entry lands alone, as the last ref change of its push, and the queue lands nothing more until `queue_postmerge_done`. While the queue owns the repo's merges, `_merged` reads only the forge's `MERGED`, so stage 3 never runs on an unmerged PR. After the landing, a Needs-you entry names `fr ops gate --run <id>`, which resumes at stage 3. Stage 4's completion adds `fr-queue:postmerge-done`, which the driver records as `queue_postmerge_done`. A combination behind the barrier may be built and tested meanwhile, but lands only after the barrier lifts.
R27. A broken hold never makes the queue land untested code or touch a PR branch. A foreign push to `main` while the hold is `open` is handled by R14. A missing, expired or foreign-`cleared` `open` hold, found while the queue is open, is re-armed on the next pass. The driver reports it once, as a Needs-you entry naming the release (tag and commit) that may have cut from a partly landed wave, if one did. A release commit that lands on `main` mid-queue is a foreign move like any other.
R28. The operator hears through three channels.
 - Needs-you entries, each with a command to paste: an entry ejected with its budget spent, a held queue (R7, R22, R31, R34, R35), a re-armed or uncleared hold (R19, R27), a stalled drain (R30), a barrier waiting on the DevOps stage longer than `queue.stall_hours`, a failed `post_merge` (R33), and a required check that never reported (R7).
 - One marker comment per queued PR (`<!-- fr-queue -->`), edited in place as its state changes: queued at position k, testing in combination <sha>, ejected (why, and what to do), landed at <sha> in wave N. It honours `forge.comments: off`.
 - A wave report at drain: the landed, ejected and deferred PRs; the CI cycles, wall time and approvals per PR; and the release the drain asked for. It goes into the wave close-out PR's body, in a section `review_reasons` ignores, and onto the Batches page.
R29. A batch can leave its wave. `fr triage batch defer <id>` takes it out of the wave's queue and its drain, records a `deferred` event naming the wave, and keeps the PR open so its session can go on. `fr triage batch requeue <id> [--wave N]` asks for it to join a later queue: wave N's (whose queue must not be open yet), or by default the next queue to open, as a between-waves entry (R2). Both verbs work through the one judgements writer and print what they changed. A deferred batch no longer holds the wave's close-out; its own close-out is owed after it lands.
R30. The driver never takes a batch out of a wave by itself; it proposes it. When every other batch of the open wave is landed, cancelled, abandoned or deferred, one batch may still block the drain because its hand-back budget is spent or it has made no progress (no new head, no landing) for `queue.stall_hours` (default 4). The driver then adds a Needs-you entry with the `defer` and `requeue` commands. A wave drains once every batch is landed, cancelled, abandoned or deferred.
R31. A repo has at most one open queue, across every scope that contains it. A driver opens a queue only when its lease on `fr-hold/queue` succeeds, which requires the ref to be absent or `cleared`. While another scope holds the hold (`open` or `drained`), it opens none, lands nothing on that repo, and reports a Needs-you entry naming the holding scope.
R32. All of the driver's merges go through the queue. A collected close-out PR, a legacy per-batch archive PR, the per-wave state-export PR and a DevOps housekeeping PR (stage 8) are queue entries. Each enters under its existing trust rule (`review_reasons`, `attributed` plus `archive_allowed`, `_export_row`'s checks) or, for a housekeeping PR, `approved-fr` recorded on the queue's events. `_archive` and `_export_merge` stop calling `pr_merge` and emit queue entries instead.
R33. `post_merge` runs once per landing, not once per batch. It runs after the landing push, from the base clone fast-forwarded to the landed `main`, with every batch that the landing merged recorded as `post_merge` done. The queue builds and tests meanwhile, but lands nothing more until it has finished. The wave close-out entry is started only after the last landing's `post_merge`. A failed `post_merge` pauses the queue's landings and is a Needs-you entry. `post_merge_restart` keeps its once-per-pass rule.
R34. Under `land: push`, the default branch must accept the driver's direct push. That means either a ruleset with no "require a pull request" rule (GitHub accepts a direct push of a commit whose required checks already passed, which a tested combination's sha has), or a bypass identity dedicated to the driver. fr never makes the operator's own credential a bypass actor, and says so in the held reason. A push refused by protection holds the queue with a reason naming both remedies and `queue.land: merge`.
R35. The queue runs on the forges whose client implements `commit_checks`, `pr_view`, `pr_merge` (for `land: merge`), `required_check_names`, label edits and comment edits: today the GitHub clients, under both `forge.api: graphql` and `rest`. A repo on glab or tea is held, naming gh#611. Gitea also needs "autodetect manual merge" enabled. After every landing push, the driver reads each landed PR back. A PR that still reads open is a Needs-you entry ("the forge did not mark #n merged"), and the queue pauses until it reads merged.
R36. While the queue is open, batch PRs that wait on a later queue (delivered, `pr-open`, their wave not open) do not count against `max_inflight`. That way an undispatched batch of the open wave is never starved by later waves' finished work.

## Design

### A. Where the queue lives

The queue is a new pure planner, `fr.triage.wave_queue`, beside `batch_drive`. It
replaces `_walk_train`'s two branches (R22) and the planning parts of the archive
and export steps (R32). `drive_pass` calls it per repo with the snapshot and gets
back actions and a `Queue` view (`train_line`'s successor, R25). Like `batch_drive`,
it reads no clock and runs no git and no forge.

Its inputs, added to `Snapshot` by the command layer:

- the repo's queue records (R24), from judgements;
- each slot's sha and its `commit_checks` verdict;
- `main`'s sha now (`bases`), each PR's live head, labels and patch-id;
- the hold ref's commit (state, scope, parent, refreshed time);
- the repo's `queue:` config;
- the `post_merge` state of the last landing.

Its actions:

- `queue-open` (the hold to `open`) and `queue-hold` (refresh, or re-arm, R27);
- `queue-build` (entries i..k on base b, slots) and `queue-land` (prefix 1..j at sha s);
- `queue-eject` (entry, why) and `queue-rebuild` (a foreign base move, R14);
- `queue-post-merge` (R33);
- `queue-drain` (the hold to `drained`, dispatch the release) and `queue-cleared`
  (record the release's clear, or clear it under `release: none`);
- `queue-held` (a repo that cannot take part: R7, R22, R31, R34, R35);
- the Needs of R28 and R30.

### B. Choosing the wave (R2, R31, R36)

A repo's queue has three phases, read from its records and the hold:

1. **open**: from `queue_open` to `queue_drain`, with the hold `open`;
2. **releasing**: from `queue_drain` until the hold is `cleared` or gone, with the
   hold `drained`;
3. **idle**: with the hold `cleared` or absent.

Only an idle repo opens a queue, and only when the leased hold push succeeds (R31).
It opens the lowest wave that has a non-terminal batch. When that wave has no entry
ready yet, the queue still opens on its first ready entry, and nothing of a later
wave enters meanwhile. With no waved batch unfinished, it takes the oldest
between-waves entry (R2, R32). Entries join an open queue in readiness order. The
wave drains once every batch of the wave is terminal (deferral included) and its
close-out, if it has one, has landed. A between-waves queue drains when its one
entry lands.

The in-flight cap (`batch_drive.py:2012`) stops counting a batch whose PR waits on a
queue that is not open (R36). Dispatch stays wave-ordered, so this only stops a
later wave's finished batches from taking the open wave's slots.

### C. Building and testing (R4–R8, R13)

The command layer executes `queue-build` in a scratch worktree under the state
directory (as `_update` does today, through `gitseam`). For each entry it applies
the method's step from R5 on top of the previous entry's commit, with R6's conflict
rules and version slot. Entry k's commit is pushed to `slot-k`, leased on the sha
the slot held, and recorded as `queue_built`. Entry k+1's commit has entry k's as
its parent, so slot k+1 holds main + 1..k+1. CI runs on each push (R7). A rebuild
with the same tree (R13) gets a new commit timestamp, so the sha differs and CI runs
again.

### D. Landing (R9–R11, R33–R35)

Under `land: push` the command issues one push:

```
git push --atomic origin \
  --force-with-lease=refs/heads/<default>:<base> <tip>:refs/heads/<default> \
  --force-with-lease=refs/heads/<head-ref>:<built-from> <entry-commit>:refs/heads/<head-ref> …
```

Under `merge` each landed head ref is pushed to its own unchanged sha, so the lease
still checks it. Each PR's head is then reachable from `main`, so the forge marks it
merged (R35 checks that it did). fr's existing readers keep working: the batch PR
reads `MERGED`, its `Closes` lines close their issues, the gate labels sit on the
merged PR, and `release.py`'s first-parent scan finds `(#n)` or
`Merge pull request #n`. A PR branch is rewritten only here, after approval and
green CI, and only under a lease on the head the combination was built from.

Under `land: merge` (R11), the command calls `pr_merge(head_sha=…)` per entry in
order, then compares `git rev-parse <default>^{tree}` with the combination's tree.

After a landing, `queue-post-merge` runs `post_merge` once (R33). The next
`queue-land` waits for it.

### E. Approval by content (R12)

`ApprovalEvent` and `UpdateEvent` gain an optional `patch_id`, and judgements schema 13
adds them. `approval_verdict` takes the live patch-id, which the command computes through
`gitseam` with exactly R12's command (`PATCH_ID_DIFF` piped to `PATCH_ID`). The verdict is
`Approved` when the live patch-id equals one recorded since the live approval (its own, or
an fr update's after it), and otherwise falls back to `reaches()`, which is `Void` for a
head fr did not push. `judge_approval` is the one reading the settle, the snapshot and the
merge gate make: on a mismatch it fetches the default branch and reads the id once more
before the verdict stands. `settle_approvals` computes the patch-id at the head it records,
and records it on a live approval that has none once the approval holds and the id reads.
fr's update of a PR branch records the new head's patch-id on its `update` event.

`git patch-id` hashes the diff's lines without their hunk line numbers. A change that
moves an otherwise identical hunk within a file therefore keeps the id, and the approval.
The design accepts that limit rather than add a position-sensitive pin, which a merge of
`main` would void and so defeat the rule.

A merge of `main` that changes the context lines around the PR's hunks changes the
patch-id and voids the approval. That is the conservative side, and the design
accepts it.

### F. Close-out per wave (R15, R16, R33)

After the last batch landing of the open wave and its `post_merge` (R33), the driver
starts the wave's collected close-out as today. Its members are the wave's landed
batches that `is_gated` reads false for, not every owed batch of the repo. A gated
batch's close-out is owed once `fr gate pass` (or DevOps stage 6) passes it, and
then queues between waves.

The close-out verb runs `fr migrate artifacts --yes --path …` over exactly the files
it archives (R16), as its own commit. `review_reasons` admits a branch whose commits
are that migration commit followed by the recorded head, provided the migration
commit changes only files the archive then moves. `archive_allowed` already accepts
the deletion out of a live directory and the addition under
`docs/superpowers/implemented/`.

### G. The hold handshake (R17–R19, R27, R31)

The hold is a branch, so plain git sees it on any forge. It is not under
`fr-queue/`, so it triggers no queue CI. `release.py` runs `git fetch origin
+refs/heads/fr-hold/queue:refs/fr-hold/queue` (no credential on a public repo; the
workflow's read token otherwise), reads the commit message, and passes the state,
scope, wave, parent and refreshed time into `fr release status --from-json`.

| State | Who writes it | Release behaviour |
|---|---|---|
| `open` | the driver, at queue open and each pass | held, unless older than 24 h (warned) |
| `drained` | the driver, after the last landing or a drain by deferral | releases; then clears the hold if its base contains the hold's parent |
| `cleared` or absent | the release, or the driver under `release: none` | nothing to do |

`release.yml` gains `push: branches: ['fr-hold/**']`, and its jobs skip a deletion
push (`github.event.deleted`). The clear runs in `publish`, or in `prepare` when it
cuts nothing, with the token those jobs already hold. It is a leased push of a
`cleared` commit (`git push --force-with-lease=refs/heads/fr-hold/queue:<drained sha>`),
so it never clears a hold that a newer queue has opened since.

Every state change of the hold is a leased push. The driver reads a lease failure on
the hold as "another writer moved it" and handles it under R27 or R31, never by
force.

### H. Validation of migratable artifacts (R21)

`fr validate artifacts --allow-migratable` treats a stale stamp with a registered
migration path as passing and prints it as `stale, migratable`. `ci.yml`'s
`validate-artifacts` job passes the flag on `pull_request` and on `fr-queue/**`
pushes, and runs without it on `main`.

### I. What is removed or changed (R22, R23, R32)

Removed:

- `_walk_merge_train`, `_walk_queue`, the `enqueue` action and its executor;
- `merge_ready`'s update path, `update_failing`, and the `reupdate` rule of `red_decision`;
- the strict-checks routine-commit exemption.

Changed:

- `_archive` and `_export_merge` emit queue entries and call no `pr_merge`.
- DevOps stage 2 adds a label instead of merging (§J).
- `batch merge` becomes "open a queue for these batches and drive it in the
  foreground until it drains or stops".

### J. Gates (R15, R26)

`gate:devops` acts before and after the merge (`PRE_MERGE_HOLD_GATES`, `gates.py:20`).
The DevOps stage keeps its eight stages, and two of them change:

- **Stage 2.** After the operator's terminal confirmation, it adds the label
  `fr-queue:release`. It records nothing, and `_merged` reads only the forge, so
  stage 2 is done when the PR reads `MERGED`.
- **Stage 4.** When it completes, it adds `fr-queue:postmerge-done`.

The DevOps stage needs no access to triage state: the driver settles both labels
into `queue_release` and `queue_postmerge_done` events, as it settles `approved-fr`.
The planner treats a `gate:devops`-held entry as a barrier. It enters only with a
`queue_release` at its current patch-id, it is the last entry of its landing, and
nothing lands behind it until `queue_postmerge_done`. After the barrier lands, a
Needs-you entry names `fr ops gate --run <id>`.

`gate:tester` acts only after the merge. A tester-gated batch lands like any entry.
The release that follows its wave is an RC (release gating, unchanged), which is
what the Tester walks.

### K. A broken hold (R27)

| What happened | What the queue does |
|---|---|
| A stray merge or push moved `main` | Rebuild on the new `main` (R14), report it once, touch no PR branch |
| The hold vanished or was cleared while `open` | Re-arm it next pass; Needs-you, naming any release cut from a partly landed wave |
| The hold expired (no driver pass for 24 h) | The same on the driver's return; the release may have cut what had landed, which is a tested state |
| A release commit landed mid-queue | A foreign move: the next landing's lease fails and the queue rebuilds |
| A drained hold was never cleared | Needs-you after `queue.release_wait_hours`, with the clear command |
| Another scope holds the hold | Open nothing, land nothing; Needs-you naming that scope (R31) |

### L. Keeping the operator in the loop (R28)

Problems go to Needs you, which the board and the pass output already carry, each
with a command to paste. Progress goes in one marker comment per queued PR, edited
in place through the `GhClient` adapter. Success goes in the wave report, rendered
purely from the queue's events, into the close-out PR's body (in a section
`review_reasons` ignores) and onto the Batches page.

### M. Leaving a wave (R29, R30)

`defer` and `requeue` are `fr triage batch` subcommands next to `edit` and `cancel`,
and they write `deferred` and `requeued` batch events. The planner reads a deferred
batch as terminal for its wave's drain, and a requeued one as an entry of the queue
it names. Stall detection is pure: it reads the batch's last head change and last
event from the snapshot, against `Snapshot.now`. It produces a Needs-you entry,
never a write.

### Config (`.fr/triage.yaml`)

```yaml
queue:
  ci: push            # push | none (none only where services say `ci none`)
  depth: 2            # combinations (slots) in CI at once
  land: push          # push | merge
  check_wait_minutes: 60  # a required check that never reports is a Need
  release: workflow   # workflow | none (none: the driver clears its own hold)
  release_workflow: release.yml   # optional: dispatched when the hold is drained
  release_wait_hours: 6           # a drained hold not cleared by then is a Need
  stall_hours: 4      # a batch blocking the drain this long is proposed for deferral
```

This repo gains the block. Its `ci.yml` and `acceptance-report.yml` gain `push:
branches: ['fr-queue/**']`, and its `release.yml` gains `push: branches:
['fr-hold/**']` with the deletion guard. No new workflow file is added, so
`.github/ci-budget.yaml` needs no entry. It keeps `merge_method: squash`: R5's squash
chain lands squash-shaped history. Its `main` ruleset must satisfy R34; the operator
picks the remedy when enabling the queue.

## Out of scope

- Flagging wave batches whose plans overlap, before they conflict (#1577).
- Red CI and conflicts on unapproved drafts (#1492, #1493). The queue takes only
  approved PRs, so those gaps stay as they are.
- #1569's second half (a retry on a held close-out branch read as reopened) and
  #1496/#1497's re-recording and approval of close-out PRs. A wave close-out held by
  `review_reasons` stays held as today.
- glab and tea adapters for the batch engine (gh#611).
- Cheaper CI per cycle (#1555, #1340).
- Skipping `main`'s own CI run after a fast-forward of an already tested commit.

## Verification

strategy: candidate
- wave-queue-live-wave: live — only a real wave on this repo exercises GitHub's merged-by-push detection, the atomic push against the real ruleset, and `release.yml` reading and clearing the hold; every other row is proven pre-merge by the fake forge over real bare git repositories.
- wave-queue-speculative-land: none — a candidate scenario never reaches a forge; the CI suite proves it over a fake forge and real bare git remotes (Test Plan 1, 8, 16), and wave-queue-live-wave walks it live.
- wave-queue-land-methods: none — needs a forge to read merged state; the CI suite proves it over a fake forge and real bare git remotes (Test Plan 2–4), and wave-queue-live-wave walks it live.
- wave-queue-wave-exclusive: none — needs forge PR state; the CI suite proves it with the pure planner and the fake forge (Test Plan 9, 18).
- wave-queue-approval-content: none — needs PR labels and heads; the CI suite proves it over a real git repo and the fake forge (Test Plan 5).
- wave-queue-eject: none — needs forge checks and sessions; the CI suite proves it with the pure planner and the fake forge (Test Plan 6, 7).
- wave-queue-one-path: none — needs forge merge state and rules; the CI suite proves it with the fake forge (Test Plan 12, 14, 15, 23, 24).
- wave-queue-devops-barrier: none — needs PR labels and the DevOps stage's forge reads; the CI suite proves it with the fake forge (Test Plan 19).
- wave-queue-broken-hold: none — needs a remote holding the hold ref and a forge; the CI suite proves it over real bare git remotes (Test Plan 20).
- wave-queue-operator-loop: none — PR comments and Needs need a forge; the CI suite proves them with the fake forge (Test Plan 21).
- wave-queue-leave-wave: none — needs a driver's forge-read snapshot; the CI suite proves it with the pure planner and the fake forge (Test Plan 22).
- wave-queue-visible: none — the queue line and board read forge state; the CI suite proves them with the fake forge (Test Plan 17).
- wave-queue-post-merge: none — needs forge merged state and a driver checkout; the CI suite proves it over real bare git remotes (Test Plan 25).

gate: wave-queue-live-wave=tester

## Test Plan

1. Fake forge plus a real bare git remote: a wave of three approved green PRs; depth 2. One pass builds main+a and main+a+b on `slot-1` and `slot-2`; no PR branch moves; once both are green, one atomic push lands them and `main` equals the tested tip. (R1, R4, R8, R9, R10)
2. The same wave under `squash`: after landing, each PR's head is its squashed commit, every commit's subject is `<title> (#n)`, and the fake forge, reading reachability, reports all three merged. Under `merge` the subjects are `Merge pull request #n …` and the heads are unchanged. (R5, R10)
3. Lease failure, under both `squash` and `merge`: a session pushes to b between build and land; the atomic push lands nothing and moves no ref; the next pass rebuilds. A server that refuses `--atomic` holds the queue. (R10, R22)
4. `land: merge`: per-PR merges at pinned heads; a forced tree mismatch stops the queue with a reason. (R11)
5. Approval by content: approved at H; the session merges `main` (same patch-id) and the approval holds; an empty commit holds it; a code edit, a whitespace-only edit and a binary edit each void it and remove the label; an old event with no patch-id follows `reaches()` until a pass records its id; a clean merge of `main` after an fr update holds it; a `main` newer than the clone's copy holds it after the refetch; a host's diff configuration (textconv, external diff, prefixes) never moves the id; and, the stated limit, a moved identical hunk keeps it. (R12)
6. Red combination: main+a+b fails twice while main+a is green; a lands, b is ejected and handed back with the combination sha; c is rebuilt on main+a; a single failure followed by a green rebuild ejects nothing. (R13)
7. Conflict during a build is handed back through `conflict_decision`; a version-file-only conflict is resolved and carries the slot. (R6)
8. Foreign push to `main`: every combination is rebuilt on the new base, no PR branch moves, the approvals hold, and the move is reported once. (R14)
9. Wave order: an approved green PR of wave N+1 waits while wave N's queue is open, and also while wave N has unfinished batches but nothing ready; a no-wave batch waits for an open wave; later waves' waiting PRs do not count against `max_inflight`. (R2, R3, R36)
10. Close-out as last entry: the queue stays open until the close-out lands; it takes only the wave's ungated batches; a stale-but-migratable cursor is migrated on the close-out branch by `fr migrate artifacts --path`, which refuses a retiring hop, and the branch passes `review_reasons`. (R15, R16)
11. Hold: `open` from queue open; the driver's push after the last landing moves it to `drained`; only the release run (or `release: none`) clears it, by a leased push; `fr release status --from-json` with a fresh `open` hold says held, with one older than 24 h warns and ignores it; `release.py` cuts nothing while `open`, including a `--version` run; a superseded run clears nothing; the workflow is dispatched on drain, and a failed dispatch only warns. (R17, R18, R19)
12. `queue.ci: none` lands each built entry with no CI wait; `queue.ci: none` is refused where services report CI. (R7, R20)
13. `fr validate artifacts --allow-migratable` passes a stale movable stamp and fails a refusing one; `ci.yml` uses it on PRs and on `fr-queue/**`. (R21)
14. A repo requiring a forge merge queue, refusing the push under `land: push`, or on glab/tea is held with a reason; a repo with no `queue.ci` is refused with what to add; a required check that never reports on `fr-queue/**` becomes a Need after `check_wait_minutes`; no `enqueue` or `update` event is written anywhere. (R7, R22, R34, R35)
15. `fr triage batch merge` drives the same engine to drain. (R23)
16. A driver killed after `queue_built` and after the land push resumes from events and the forge without landing twice; the slot branches are reused, never multiplied. (R4, R24)
17. The pass line, the board and the Batches page show the queue line; a queued, approved PR is never "awaiting approval". (R25)
18. Wave sequencing: wave N drains, the hold reads `drained`; wave N+1's approved green PRs stay waiting; the release run clears the hold (once each for an RC, a final, and "nothing installable"); the next pass opens wave N+1's queue. A wave that drains by deferral, and one landed by `land: merge`, both reach the release through the `drained` push. A failed release run leaves the hold, and after `release_wait_hours` it is a Need. (R2, R17, R18, R19, R29)
19. Gates: a `gate:devops` PR enters only after `fr-queue:release` is settled to `queue_release`, lands alone, and nothing lands behind it until `queue_postmerge_done`; `_merged` reads only the forge, so stage 3 waits for the merge; a combination behind it is tested meanwhile. A `gate:tester` batch lands, is left out of the wave close-out, and its own close-out queues between waves after `fr gate pass`. (R15, R26)
20. Broken hold: a deleted or cleared `open` hold is re-armed with one Need; an expired one the same; a release commit landing mid-queue fails the next lease and the queue rebuilds; no case lands an untested tree or moves a PR branch. (R27)
21. Channels: each Need of R28 appears with its command; the PR marker comment is edited in place through queued, testing, ejected and landed (and is absent under `forge.comments: off`); the wave report lists landed, ejected and deferred PRs with their cycles and approvals. (R28)
22. Leaving: `defer` takes a batch out of the drain, so the wave drains and its close-out leaves it out; `requeue --wave N+1` puts it in N+1's queue; `requeue` alone makes it a between-waves entry; a stall past `stall_hours`, or a spent budget, gives one Need with both commands and never an automatic deferral. (R29, R30)
23. Two scopes containing one repo: the second driver's hold lease fails, it opens nothing, lands nothing and reports the holding scope. (R31)
24. Other merges: a collected close-out, an export PR and a housekeeping PR each land through the queue under their trust rule; `pr_merge` is never called outside `land: merge`. (R32)
25. `post_merge` runs once per landing at the landed `main`, records every batch it covered, gates the next landing, and a failure pauses landings with a Need. A landed PR the forge still shows open pauses the queue with a Need. (R33, R35)
26. Post-merge, live: the next wave on this repo drains through the queue; record the number of PR updates (expected 0), CI cycles per PR, approvals per PR (expected 1), and releases cut (expected 1 for the wave). (all; row `wave-queue-live-wave`)

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-19-wave-merge-queue | `derio-net/super-fr` | `2026-11-19-wave-merge-queue` | — |
