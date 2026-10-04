# Drive merges ready PRs as a merge train

**Date:** 2026-10-04
**Branch:** `feat/batch-drive-merge-train`
**Issue:** derio-net/super-fr#942 (follows #927)

## Background

`fr triage batch drive` (wave-driver spec, `docs/superpowers/implemented/specs/2026-10-02-wave-driver-design.md`)
merges ready batch PRs in step 1 of every pass. `fr.triage.batch_drive.drive_pass` emits one `merge` action for
**every** open, non-draft PR whose checks are green (`batch_drive.py:304-323`). The driver then calls
`fr.triage.batch_merge.merge_ready` for each one (`triage_batch_cmd.py:1774`). A PR that is behind its base is
updated (`_land` → `_update`, `batch_merge.py:252-262`): `main` is merged into the branch and pushed, and CI starts
again.

#927 (PR #933) stopped release commits and archive merges from counting as "behind" (`_behind_only_routinely`,
`batch_merge.py:297`). A real merge still moves `main`, though, and the next pass then updates every other ready PR
that is now behind. Each update costs a full CI run, and all of them run at once. Only one of those PRs merges next,
and the rest go behind again. In the 2026-10-04 bugfix wave PRs were updated up to eight times without merging, and
one had to be merged by hand.

## Requirements

R1. In each pass, the driver handles a repo's ready batch PRs as a merge train: the open, non-draft PRs of the drive's selection in that repo, in `merge_order` (explicit `order`, then the existing arrangement). The train is worked out separately for each repo, because each repo has its own base branch.
R2. Only the train's head is acted on. It is merged when its checks are green and it is up to date, or behind only by routine commits per #927. It is updated when it is behind. When its checks are pending, the driver waits on it. PRs behind the head are never updated or merged while they are not the head.
R3. When the head merges, the next PR in the train becomes the head in the same pass and gets the same treatment. The train stops for that repo at the first head that did not merge: it was updated, it is pending, or its head moved since it was collected.
R4. A PR whose checks fail is reported once per head sha, as today, and stepped over: the next PR becomes the head. A head the driver refuses to merge (a `MergeStopError`: an unresolvable conflict, a version below main's, a forge refusal) is also reported once and stepped over. A PR that turned draft between the snapshot and the merge is stepped over silently.
R5. The train is worked out again from merge order on every pass, and nothing about it is stored between passes. A stepped-over PR that is green again takes back its place in merge order, even when that puts it ahead of a head whose CI is still running.
R6. Every pass prints one train line per repo that has a train, before its action lines, in plan mode and when acting. The line names the head, the PRs queued behind it, and the PRs stepped over. The summary line adds `queued N`: the train members that did not merge and were not stepped over this pass, the head excluded.
R7. The train never waits on a close-out. Close-outs are started and archive PRs merged exactly as today. Close-out shapes, and running a Test Plan before merge, belong to #818.
R8. `fr triage batch merge` (the blocking queue command) is unchanged. It already merges one PR at a time and waits for each.

## Design

### A. The pure pass decides the train (R1, R2, R4 checks, R5)

`drive_pass` keeps its four steps. Step 1, merge, becomes a train walk:

1. Group `merge_order(snap.queue)` by `snap.repos[batch]`. The order comes from the full queue, so a repo's train
   keeps `merge_order`'s relative order. Within a repo, the walk goes in that order. Entries outside the selection
   are skipped, as today.
2. For each entry, look up its live PR:
   - missing, not `OPEN`, or a draft: **not a member** (skipped silently, as today);
   - `checks == "failing"`: **stepped over**, with a `warn` action once per head sha (unchanged);
   - `pr.head != entry.pr.head_oid` (moved since collect): the **head waits**. No action, and the walk stops;
   - `checks == "pending"`: the **head waits**. No action, and the walk stops;
   - green: a `merge` action. The first one is the head, and each later green member is a candidate for the same
     pass (R3). The walk continues.
3. Members after the stop are **queued**.

This adds a `Train` record to `Pass`:

```python
@dataclass(frozen=True)
class Train:
    repo: str
    head: str | None          # batch id: the first merge candidate, or the waiting head
    candidates: tuple[str, ...]  # batches with a merge action, in order (head first when it is green)
    queued: tuple[str, ...]   # batches behind the stop
    stepped: tuple[str, ...]  # batches stepped over (failing)
```

`Pass.trains: tuple[Train, ...]` is ordered by repo. Every `merge` action carries `train=<repo>`, which the
executor uses (B). The plan-mode summary is still optimistic: every candidate counts as landing, as every merge did
before. `Summary` gains `queued: int`, which is `len(queued)` summed over trains. A waiting head is not counted (R6).

Rejoining (R5) needs no code. The walk starts from `merge_order` on every pass, so a PR that is green again is back
in its place.

### B. The executor stops a train at the first head that does not merge (R3, R4)

`_Driver` keeps one more set for the pass, `_stopped: set[str]` (repos whose train stopped). It is reset alongside
`_unlanded` in `run_pass`. In `_act`, a `merge` action whose `train` is in `_stopped` is not attempted. Its outcome
is `queued: behind <head batch>`, and the batch is added to `_unlanded`, so `settle` keeps it in flight (and counts
it as queued, below). Outcomes of `_merge_batch`:

| outcome | train |
|---|---|
| merged / already merged | continues: the next candidate is the head |
| updated (pushed) | **stops**: the head waits for its new CI |
| held: head moved since checks were judged | **stops** |
| held: `pending` (checks changed since the snapshot) | **stops** |
| held: `failing` | stepped over: continues |
| held: `draft` | stepped over: continues |
| stopped: `MergeStopError` (refusal) | stepped over: continues, still reported once per batch, head and reason |

`_merge_batch` returns whether its outcome stops the train. `_act` records that in `_stopped` and remembers the head
that stopped it, for the `queued` line.

`settle` gains `queued: int = 0` and adds it to `Summary.queued`. `run_pass` passes the number of merge actions
answered with `queued`. The head that stopped the train is not counted.

### C. Output (R6)

`train_line(train)` in `batch_drive.py`:

```
train derio-net/super-fr: head a (PR #12) · queued b (#13), c (#14) · stepped over d (#15)
```

Empty parts are left out. A train with no head (every member stepped over) reads
`train <repo>: no head · stepped over …`. `run_pass` prints each train line before the action lines, in plan mode
and when acting, so `--once`, the loop and plan mode show the same train. `summary_line` appends `, queued N` when
N > 0, the same way it already appends `blocked`.

### D. Not changed

- `merge_ready`, `_land`, `_behind_only_routinely` and the update itself (#927's routine-commit rule stays as it is).
- Close-out, archive, and dispatch steps of the pass (R7). A merge that does not land still holds a dependent's
  dispatch (`_unlanded`, rg-1), which now includes queued candidates.
- `fr triage batch merge` (R8).

### E. Tests

Unit, pure (`tests/unit/test_triage_batch_drive.py`):
- three green ready PRs in one repo: three `merge` actions in merge order, with one train whose head is the first;
- head pending: no `merge` action for any member, and the rest are queued;
- head moved: the train waits, with no action;
- failing first member: `warn` once, stepped over, and the next green one is the head;
- two repos: two independent trains, each with its own head;
- a previously stepped-over PR that is green again is the head again (R5);
- `train_line` and `summary_line` with `queued`.

Command level (`tests/unit/test_triage_batch_drive_cmd.py`, fake `merge_ready` outcomes):
- head `updated`: the later candidates print `queued: behind <head>` and are never passed to `merge_ready`;
- head `merged`: the next candidate is attempted in the same pass;
- head `MergeStopError`: reported, and the next candidate is attempted;
- head `pending`/`head moved`: the train stops;
- trains in two repos: a stop in one does not stop the other;
- the summary counts queued members, and the train line is printed before the actions in plan mode and with
  `--yes`.

### F. Acceptance rows

- `drive-merge-train-head-only` (R1-R3): only the head of each repo's train is merged or updated, and the train
  advances past a merged head in the same pass.
- `drive-merge-train-step-over` (R4, R5): failing or refused PRs are stepped over and rejoin by merge order.
- `drive-merge-train-output` (R6): train line and queued count.
- `drive-merge-train-live-wave` (R2, verify: post-merge): in a live wave of several ready PRs, each PR is updated
  at most once per merge ahead of it.

## Test Plan

Post-merge, operator-driven: drive the next wave of three or more ready batch PRs in one repo with
`fr triage batch drive --yes`. Check that each pass prints one train line. Check that only the head is updated after
each merge. Check that no PR is updated more than once for each PR merged ahead of it. Flip
`drive-merge-train-live-wave` with the observation.
