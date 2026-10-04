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

R1. In each pass, the driver handles a repo's ready batch PRs as a merge train: the open, non-draft PRs of the drive's selection in that repo, ordered by wave, then `order`, then batch id (unset values last), the key `drive_pass` already sorts dispatch by. This order is stable when a member leaves the train. `merge_order`'s overlap-minimising arrangement is not, so the train does not use it. Each repo has its own base branch, so each repo has its own train.
R2. Only the train's head is acted on. It is merged when its checks are green and it is up to date, or behind only by routine commits per #927. It is updated when it is behind. When its checks are pending, the driver waits on it. PRs behind the head are never updated or merged while they are not the head.
R3. When the head merges, the next PR in the train becomes the head in the same pass and gets the same treatment. The train stops for that repo at the first head that did not merge: it was updated, it is pending, or its head moved since it was collected or judged.
R4. A PR whose checks fail is reported once per head sha, as today, and stepped over: the next PR becomes the head. A head the driver refuses to merge (an unresolvable conflict, a version below main's, a forge refusal) is also reported once and stepped over. A PR that turned draft, closed or merged between the snapshot and the merge is no longer a member, and the train moves on.
R5. The train is worked out again from its order on every pass, and nothing about it is stored between passes. A stepped-over PR that is green again takes back its place in that order, even when that puts it ahead of a head whose CI is still running.
R6. Every pass prints one train line per repo that has a train, before its action lines, in plan mode and when acting. The line names the head, the green PRs planned to follow it this pass, the PRs queued behind the stop, and the PRs stepped over. The summary line adds `queued N`: the members that will not be attempted this pass and were not stepped over, the head excluded.
R7. The train never waits on a close-out. Close-outs are started and archive PRs merged exactly as today. Close-out shapes, and running a Test Plan before merge, belong to #818.
R8. `fr triage batch merge` (the blocking queue command) keeps its behaviour. It already merges one PR at a time and waits for each.
R9. The fr-triage skill's description of the driver states the merge train, in its canonical source and both generated mirrors.

## Design

### A. The pure pass decides the train (R1, R2, R4 checks, R5)

`drive_pass` keeps its four steps. Step 1, merge, becomes a train walk:

1. Sort `snap.queue` by `_dispatch_key(entry.batch)` (wave, then `order`, then id), then group the entries by
   `snap.repos.get(batch, "")`, keeping that order within each repo. Entries outside the selection are skipped, as
   today. `merge_order` is no longer used here: its arrangement depends on which entries are in the queue, so a head
   that merged and left could reorder the members after it, and a second PR would be updated (review spr-order-unstable).
2. Walk each repo's entries, looking up each one's live PR:
   - missing, not `OPEN`, or a draft: **not a member** (skipped silently, as today);
   - `checks == "failing"`: **stepped over**, with a `warn` action once per head sha (unchanged);
   - `pr.head != entry.pr.head_oid` (moved since collect) or `checks == "pending"`: **the walk stops here**. No
     action. If no candidate came before it, this member is the (waiting) head. Otherwise it is the first **queued**
     member;
   - green: a `merge` action carrying `train=<repo>`. The first one is the head. Each later one is a candidate for
     the same pass (R3), and the walk continues.
3. Every member after the stop is **queued**, except a failing one: it is stepped over and warned wherever it sits,
   so its failure is reported at once instead of when it reaches the front (review rv-queued-failing-unwarned).

This adds a `Train` record to `Pass`:

```python
@dataclass(frozen=True)
class Train:
    repo: str
    head: str | None                 # the first candidate, or the waiting head; None when every member was stepped over
    candidates: tuple[str, ...]      # batches with a merge action, in order (head first when it is green)
    queued: tuple[str, ...]          # the member that stopped the walk (when it is not the head), then every later one
    stepped: tuple[str, ...]         # batches stepped over (failing)
    numbers: Mapping[str, int]       # batch id -> PR number, for train_line
```

`Pass.trains: tuple[Train, ...]` is ordered by repo. The plan-mode summary is still optimistic: every candidate
counts as landing, as every merge did before. `Summary` gains `queued: int`, which is `len(queued)` summed over
trains. A waiting head is not counted (R6).

Rejoining (R5) needs no code. The walk starts from the same stable order on every pass, so a PR that is green again
is back in its place.

### B. The executor stops a train at the first head that does not merge (R3, R4)

`_Driver` keeps two more per-pass fields, reset alongside `_unlanded` in `run_pass`:
- `_stopped: dict[str, str]`, mapping a repo to the batch whose outcome stopped its train;
- `_queued: int`.

In `_act`, a `merge` action whose `train` is in `_stopped` is not attempted. Its outcome is `queued: behind <batch>`,
the batch is added to `_unlanded` (so `settle` keeps it in flight, and a dependent's dispatch stays held, rg-1), and
`_queued` goes up by one. `_merge_batch` also returns whether its outcome stops the train. One function beside it
makes that decision:

| outcome | train |
|---|---|
| merged / already merged | continues: the next candidate is the head |
| updated (pushed) | **stops**: the head waits for its new CI |
| held: head moved since checks were judged (`slots[0].head != action.head`) | **stops** |
| `HeadMovedError` from `merge_ready` (moved between plan and re-read) | **stops**, reported once |
| held: `pending` (checks changed since the snapshot) | **stops** |
| held: `failing` | stepped over: continues |
| held: `draft`, or `MergeStopError` for a PR no longer OPEN | no longer a member: continues |
| `MergeStopError` (conflict, version, forge refusal) | stepped over: continues, still reported once per batch, head and reason |

`HeadMovedError` is a new subclass of `MergeStopError` in `batch_merge.py`. `_open_head` raises it, instead of the
plain error, for "head moved since the plan was printed" (`batch_merge.py:244-248`). Every existing caller catches
`MergeStopError`, so `merge_one` and `fr triage batch merge` behave as before (R8). This lets the driver tell the
moved head, which R3 says stops the train, from a refusal, which R4 says is stepped over (review
spr-mergestop-head-moved).

`settle` gains `queued: int = 0` and adds it to `Summary.queued`. `run_pass` passes `self._queued`. The batch that
stopped the train is not counted.

### C. Output (R6)

`train_line(train)` in `batch_drive.py` takes its PR numbers from `Train.numbers`:

```
train derio-net/super-fr: head a (PR #12) · then b (#13), c (#14) · queued d (#15) · stepped over e (#16)
```

`then` lists `candidates[1:]`, the green members planned to merge after the head in the same pass. Empty parts are
left out. A train with no head (every member stepped over) reads `train <repo>: no head · stepped over …`.
`run_pass` prints each train line before the action lines, in plan mode and when acting, so `--once`, the loop and
plan mode show the same train. `summary_line` appends `, queued N` when N > 0, between `closing` and `blocked`.

### D. Changed elsewhere, and not changed

- Changed: `plugins/super-fr/skills/fr-triage/SKILL.md`'s driver sentence ("each pass merges every green non-draft
  batch PR") describes the merge train instead. `scripts/sync-opencode.py` and `scripts/sync-hermes.py` regenerate
  its mirrors (R9).
- Changed, compatibly: `batch_merge._open_head` raises `HeadMovedError`, a subclass of `MergeStopError` (B).
- Not changed: `merge_ready`'s outcomes, `_land`, `_behind_only_routinely` and the update itself (#927's
  routine-commit rule stays as it is).
- Not changed: the close-out, archive and dispatch steps of the pass (R7).
- Not changed: `fr triage batch merge` and its `merge_order` (R8).

### E. Tests

Unit, pure (`tests/unit/test_triage_batch_drive.py`; `_snap` gains an optional `repos` override for the two-repo
case):
- three green ready PRs in one repo: three `merge` actions in train order, one train whose head is the first;
- head pending: no `merge` action for any member, and the rest are queued;
- head moved: the train waits, with no action;
- green, then pending, then green: one merge action, and the pending member and the one after it are queued;
- failing first member: `warn` once, stepped over, and the next green one is the head;
- two repos: two independent trains, each with its own head;
- order stability: with members a, b, c (where `merge_order` would arrange them differently once a leaves), after a
  merges, b is still the head on the next pass;
- a previously stepped-over PR that is green again is the head again (R5);
- `train_line` (including `then`) and `summary_line` with `queued`.

Unit (`tests/unit/test_triage_batch_merge_ready.py`): a moved head raises `HeadMovedError`, which is still a
`MergeStopError`.

Command level (`tests/unit/test_triage_batch_drive_cmd.py`, fake `merge_ready` outcomes):
- head `updated`: the later candidates print `queued: behind <head>` and are never passed to `merge_ready`;
- head `merged`: the next candidate is attempted in the same pass;
- head refused (`MergeStopError`): reported, and the next candidate is attempted;
- head `HeadMovedError`, `pending`, or held as moved: the train stops;
- head `failing` or `draft` at merge time: the next candidate is attempted;
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

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-04-drive-merge-train | `derio-net/super-fr` | `2026-10-04-drive-merge-train` | — |
