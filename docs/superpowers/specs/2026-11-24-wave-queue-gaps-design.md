# Wave merge queue — hand-backs onto the slot ahead, overlap-aware waves, operator entries

Issue: derio-net/super-fr#1677. Builds on #1602 (the wave merge queue, spec
`2026-11-19-wave-merge-queue-design.md`) and #1647 / PR #1669 (CI economy, spec
`2026-11-24-ci-economy-design.md`), whose `generated:` globs this spec reads.

## Background

The wave merge queue (`fr.triage.wave_queue`, executed by `fr.triage.queue_exec`) builds
one combination per entry on `fr-queue/<scope>/slot-<k>` and lands the green prefix by a
fast-forward of `main`. Three gaps remain.

1. **A conflict hand-back names `origin/main`.** A real conflict met while building entry
   k (`queue_exec.build`, raising `MergeConflictError`, caught in `QueueExecutor._build`,
   `queue_exec.py:1271`) becomes a `BuildConflict(head, paths, reason)` and a `queue-eject`
   action (`wave_queue._plan_open`, `wave_queue.py:896-911`). For a batch it goes through
   `_Driver._queue_hand_back` → `_conflict` → `conflict_decision` → `_hand_back`
   (`triage_batch_cmd.py:6966`, `:6330`, `:6602`), whose brief is
   `batch_dispatch.conflict_brief(..., base=ctx.main)` (`batch_dispatch.py:279`):
   "`git fetch origin && git merge origin/main`". The commit the entry was built on
   (`prev` in `build`, the combination of the entries ahead, or the queue's base) is not
   named. A session that merges `main` while entries ahead are still queued conflicts
   again once they land. On 2026-11-24 merging the slot commit by hand (`24130aa17`,
   #1628 ahead of #1630) made #1630 land-ready the moment #1628 landed at that sha.
   `conflict_decision` (`batch_drive.py:919`) skips any head that already has a
   `ConflictEvent`, so nothing re-issues a brief whose commit an ejection ahead rebuilt.
2. **Waves ignore file overlap.** `batch.suggest` (`batch.py:780`) groups free issues by
   cited path, theme and pattern; `batch create --wave` and `batch edit --wave`
   (`triage_batch_cmd.py:914`, `:964`) write the wave with no look at what the wave's
   other batches change. `batch.merge_order` (`batch.py:845`) already reads PR files for
   the old train's order. Overlapping batches in one wave serialise through hand-backs.
3. **Only fr's own PRs enter the queue.** Batch PRs, and the R32 entries (`OtherEntry`:
   `closeout`, `export`, `archive`, `housekeeping`; `QueueEntryKind`, `model.py:1109`)
   admitted by `batch_drive` step 3 (`batch_drive.py:2106`). A housekeeping PR is
   admitted by `_Driver._housekeeping_reads` (`triage_batch_cmd.py:7241`): open, head ref
   `chore/ops-`, trusted author (`distrust`), approval settled on the queue's own
   `approval` events (`approval.settle_entry_approval`, `approval.py:320`). Any other PR
   is merged by hand, which re-conflicts every queued PR, or never.

PR #1669 adds `TriageConfig.generated` (the globs of files the repo's `mirrors:` write in
whole), `fr.triage.regen.outside_generated`, and a `Regen` port to `queue_exec.build`. The
module line budgets (`tests/unit/test_tripwire_module_budget.py`) leave `batch_drive.py`
and `triage_batch_cmd.py` a few lines each, so new logic lives in new modules.

## Requirements

R1. When the queue ejects an entry for a real conflict met while building it, the hand-back names the commit the entry was being built on: the slot ref `fr-queue/<scope>/slot-<k-1>` and its sha, or the default branch and its sha when the entry was first in the queue. The brief tells the session to merge that commit, not `origin/main`.
R2. The `conflict` event records that commit (`onto`). While the entry's head is unchanged, the driver re-issues the brief when the recorded commit no longer leads to `main`: it is not the queue's base, a standing combination, or a `main` the queue landed. That happens when an entry ahead is ejected or `main` moves outside the queue. The new brief names the commit the entry will now be stacked on: the last standing combination, else the base.
R3. A re-issued brief is recorded as a `conflict` event marked `reissue` at the same head, and never counts against the hand-back budget. A head whose latest `conflict` event names a commit that still leads to `main` is not briefed again.
R4. An entry whose head reaches a combination commit the queue recorded (`queue_built`) that no longer leads to `main` is never built, whatever its approval. It carries an ejected entry's change. The driver holds it out of the queue and briefs its session once per head: reset the branch to the head of its last hand-back, push with `--force-with-lease`, then merge the commit named by R2. This is the one brief that allows a force-push.
R5. For an entry that is not a batch, the hand-back of R1, R2 and R4 is a Needs-you entry naming the commit to merge, sent to the operator as today's "the operator's" line.
R6. A batch's expected change set is its PR's changed files when a PR exists, else the file paths its members' judgement details and issue bodies cite (`cited_paths`, untrusted issues skipped). Paths matching the repo's `generated:` globs or `version.files` are left out. Two cited paths name one file when one is a path suffix of the other.
R7. `fr triage batch suggest` lists each pair of batches in one wave whose expected change sets overlap, with the wave, the shared paths and two remedies: merge them into one batch, or move one to another wave (naming the next wave number).
R8. `fr triage batch create --wave` and `batch edit --wave` write the batch, then print every overlapping pair the new or moved batch forms in its wave, in R7's form. They never refuse for an overlap.
R9. The dispatch brief of a batch that overlaps an earlier batch of its wave names that batch and the shared paths. It also tells the session that the queue builds it after that batch and hands any conflict back with the commit to merge. A batch is earlier by the driver's dispatch order: order, then id.
R10. `fr triage queue add --pr <n> [--repo R] [--preapproved]` records a `queue_add` event naming the PR, the forge login that the command authenticates as, and whether it is preapproved. It refuses a PR that is not open, whose base is not the default branch, whose branch is in another repository, whose author the repo does not allow, or that is already added. A batch PR of the scope is already an entry: only `--preapproved` is accepted for one, and it records the preapproval alone.
R11. `fr triage queue remove --pr <n> [--repo R]` records a `queue_remove` event with the same login. It refuses a PR that is not added. An added PR in a combination is ejected with reason `operator`.
R12. An added PR is a queue entry of kind `operator`. It is admitted only under the rules a housekeeping PR has: open, same-repo branch, allowed author, a valid `approved-fr` recorded on the queue's `approval` events and pinned to the patch-id (R12 of #1602), and its own head's checks green. It is stacked, tested, landed and reported like any other entry.
R13. For a preapproved PR (added and not removed), the driver adds `approved-fr` itself and records the approval at the live head and patch-id. It does so when the PR's own head checks are green, the forge does not read it as conflicting, and no queue conflict is recorded at that head. Any later void follows the usual rule. The driver approves again at the next head that meets the same conditions, for as long as the PR stays added.
R14. An added PR joins whichever queue of its repo is open, whatever that queue's wave. When none is open, a ready added PR opens a one-entry between-waves queue at once, even while waves have unfinished batches, provided the lowest unfinished wave has no ready entry. Otherwise that wave's queue opens and the added PR joins it.
R15. An open queue does not drain while an added PR is pending: added, not removed, open and not landed. The drain, the hold's `drained` push and the release that follows therefore include it. A pending added PR that blocks the drain for `queue.stall_hours` is a Needs-you entry naming `fr triage queue remove --pr <n>`.
R16. The `queue_add` and `queue_remove` events and the `conflict` event's `onto` and `reissue` fields are new shapes of the triage state. They need judgements schema 14, which fr reads from 1 to 14 and writes.

## Design

### A. The commit ahead (R1–R5)

`MergeConflictError` (raised in `queue_exec.build`) gains the commit the entry was built on,
`onto`, and its slot number (0 for the base). `BuildConflict` gains the same two fields,
and so does the `queue-eject` action (`QueueAction.base`, `slots`), so the command layer
can name `fr-queue/<scope>/slot-<k-1>` and its sha. `conflict_brief` takes `onto` (a sha)
and `onto_ref` (the slot ref or `origin/<default>`) in place of `base`. Its step 2 reads
"`git fetch origin <onto_ref>`, then `git merge <onto sha>`", and it says why: that
commit is what `main` becomes when the entries ahead land.

Lineage is pure and is read from the queue record (`wave_queue.replay`). A commit leads to
`main` when it is the record's base now, a standing combination's sha, or a
`queue_land.main` of the record. A new pure module, `fr.triage.queue_handback`, holds:

- `stack_target(record, rep, key)`: the commit an ejected entry would be stacked on now
  (the last standing combination, else the base) and its slot;
- `reissue_due(batch_events, head, lineage)`: true when the latest `conflict` event at
  `head` names an `onto` outside the lineage;
- `stale_carry(key, carried, lineage)`: the recorded combination shas a head reaches that
  are outside the lineage. The command layer computes `carried` per entry head with
  `gitseam` (`merge-base --is-ancestor` over the record's `queue_built` shas) and passes
  it in a new `QueueSnapshot.carries` mapping.

`_plan_open` asks `queue_handback` for two actions. `queue-reissue` covers an ejected
entry at its ejected head whose `onto` went stale (R2). `queue-carry` covers an entry
whose head carries a stale combination (R4); such an entry is also dropped from
`entries` before the build window is chosen. The executor and `_Driver` deliver both
through the existing hand-back path (session, fresh conflict session, or held). A
re-issue writes `ConflictEvent(reissue=True, onto=…)`. `handbacks_since` counts only
events without `reissue` (R3), and `conflict_decision`'s skip rule becomes "a `conflict`
event at this head whose `onto` is still in the lineage, or that has no `onto`". The brief
for R4 is `carry_brief`, beside `conflict_brief` in `batch_dispatch`. A non-batch entry
gets the same words as a `queue-need` (R5).

### B. Overlap (R6–R9)

A new pure module, `fr.triage.wave_overlap`:

- `expected_paths(batch, judgements, facts) -> frozenset[str]` (R6);
- `wave_overlaps(batches, judgements, facts, *, only=None) -> list[Overlap]`, where
  `Overlap(wave, first, second, paths)` puts `first` earlier by dispatch order (order,
  then id). With `only`, it returns just the pairs that batch forms;
- `overlap_line(o, next_wave)`, the R7 sentence.

`batch suggest` prints the overlap lines after its groupings, `create`/`edit` print them
after the write (R8), and `batch_dispatch`'s brief adds the R9 line for each `Overlap`
whose `second` is the batch being dispatched. Only open batches count (`is_open`).

### C. Operator entries (R10–R15)

**State.** `Judgements` gains `queue_requests: list[QueueAddEvent | QueueRemoveEvent]`.
Each event has `kind`, `at`, `repo`, `scope`, `pr`, `by` and `preapproved` (the add only).
`fr.triage.queue_requests` (pure) folds them: `added(requests, repo, scope)` gives each
PR whose latest event is an add, with its preapproval, its add time and who added it.
`QueueEntryKind` gains `operator`.

**Verb.** `fr triage queue add|remove`, in a new `commands/triage_queue_cmd.py`
registered on the triage app. It reads the PR through the `GhClient` adapter
(`pr_view`), the allowed authors as `_housekeeping_reads` does, and the login from the
client (`GhClient.viewer_login`, `ghclient.py:469`, which both GitHub clients already
implement). It writes
through the one judgements writer. Both verbs print what they changed.

**Driver reads.** A new `_Driver` collaborator module, `fr.triage.operator_entries`,
mirrors `_housekeeping_reads` for the added PRs: it settles the approval on the queue's
`approval` events with `QueueEntryRef(pr=n, kind="operator")`, applies R13's
preapproval with `--yes`, and returns the admitted `(LivePr, at)` pairs and the pending
PRs. `batch_drive` step 3 gains one `Admitted("operator", …)` loop. Its few lines are
the only `batch_drive.py` growth, within budget.

**Planner.** In `wave_queue._cands`, an `operator` entry takes the open queue's wave
(R14). `_plan_idle_open` lets a ready operator entry open a between-waves queue while
the lowest unfinished wave has no ready entry (R14). `_drained` refuses while
`QueueSnapshot.pending_operator` (new) names a PR (R15). The stall Need reads the add
time against `stall_hours`. A removed PR that is in a combination is ejected with reason
`operator` (R11).

### D. Schema (R16)

Judgements schema 14: `_EVENT_SCHEMAS` registers `queue_add` and `queue_remove` at 14.
The writer stamps 14 when a file carries a request or a `conflict` event with `onto` or
`reissue`, and fr reads 1–14. Triage state is not an artifact kind, so artifact-versioning's
migration rule does not apply (as in #1602).

## Out of scope

- Moving batches between waves automatically. fr reports overlaps and never edits a
  wave by itself.
- Red ejections (R13 of #1602) keep `red_decision` as today.
- A tracker-wide overlap check across repos. Overlap is per repo, per wave.

## Verification

strategy: candidate
- wave-queue-handback-slot: none — proven by the CI suite: the pure planner over queue records, and the hand-back over a fake forge and real bare git remotes.
- wave-queue-handback-carry: none — proven by the CI suite over real bare git remotes (the ancestry read) and the pure planner.
- wave-queue-overlap-report: none — proven by the CI suite: the pure overlap module and the CLI over fixture facts.
- wave-queue-operator-entry: none — proven by the CI suite with the fake forge and the pure planner.
- wave-queue-operator-preapproval: none — proven by the CI suite with the fake forge (labels, checks, mergeable state).
- wave-queue-gaps-live: live — only a real wave on this repo shows a hand-back merged onto the slot commit landing without a second conflict, and an operator-added PR shipping in the wave's release.

gate: wave-queue-gaps-live=tester

## Test Plan

1. Post-merge, live: in the next wave on this repo, a conflict hand-back names `fr-queue/<scope>/slot-<k-1>`; after the session merges it, the PR lands with no second hand-back; a PR added with `fr triage queue add` lands in the same wave and is in the release the drain starts. (row `wave-queue-gaps-live`)
