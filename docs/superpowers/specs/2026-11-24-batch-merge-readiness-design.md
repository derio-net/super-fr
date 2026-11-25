# Batch merge readiness — merge only what delivered, and say so per PR

Batch `merge-readiness`: super-fr#1578 and super-fr#1581, one PR.

## Background

On 2026-11-19 (batch docs-wording, PR #1560) the wave driver marked an approved green
**draft** batch PR ready and merged it while its run's cursor still read
`deliver: running`; `fr isolation gc` then reaped the workspace under the still-running
suite. The merge decision (`fr.triage.wave_queue._ready`,
`packages/fr/src/fr/triage/wave_queue.py:364`) admits a batch entry on `pr-open`, a valid
approval, a green head and no pre-merge gate. It never reads the run cursor, so
`approved-fr` alone outranks the run's own signal that it has not delivered. The member
classification that feeds the board (`batch_drive.py:1595-1625`) makes the same call.

The operator then had to assemble every readiness answer by hand from five sources
(cursor, checks, mergeable state, approval head, session pane). The Batches page
(`fr.triage.kanban.build_board` → `kanban_render`) already runs the driver's own pass
plan over the facts (`kanban.py` `_default_plan`) and turns its `awaiting`/`queued`/`ready`
sets into one hint per card, but no card says *why* a PR is not ready or whose move it is.

What exists to build on:

- `fr.triage.cursor` reads the run cursor at an open batch PR's head
  (`cursor_position`, `read_cursor`; kind `deliver-done`), and `collect` stores it on the
  open PR (`PullRequest.cursor`, `collect.py:1003`). The board's lanes already read it
  (`lanes.py:41-58`).
- Approval is pinned to content (`fr.triage.approval`, wave-merge-queue R12): a push
  that changes the PR's diff voids it. The `deliver` resolve commits the run cursor, so an
  approval given before delivery is voided by that commit.
- fr-debugging has no run cursor at all (`plugins/super-fr/skills/fr-debugging/SKILL.md`
  §3: "There is no cursor here"), so a debug batch's PR carries no `deliver` to read.
  super-fr#1655 (S3 of the event-driven epic) makes every ad-hoc flow a workflow with
  stations and staffing; it depends on S1 and S2 and is not started.

## Requirements

R1. A batch PR is **delivered** only when every run cursor at the PR's current head that names the PR's branch records `deliver` done. Not delivered, each with its own reason: a cursor at another step (the run and step), no cursor naming the branch, the head could not be read, the repo has no clone the driver can read, or the cursor was read at a different head than the live one.
R2. The wave driver never marks a batch PR ready, never admits it to the merge queue and never merges it while it is not delivered, whatever its approval, draft state and checks. An approved green PR that is not delivered is held as "approved, not delivered".
R3. Approval keeps its current rule (pinned to the PR's content). A push after an approval that changes the diff, the `deliver` resolve's own commit included, voids it, and the page says so, naming the push's sha, and says to re-label once the PR reads Ready for approval.
R4. One pure function decides a batch PR's readiness, and its `admits` is exactly the queue's admission of that batch entry. The queue, the driver's member classification and the Batches page all call it, so given the same inputs the page never shows a verdict the driver would contradict. The page's inputs are the collected facts. Where they lag the driver's live reads (required checks, the approval's patch-id, the PR's base), the page shows when the facts were collected.
R5. The verdict is exactly one of these, decided in this order, first match wins: **Not ready: queue held: <reason>** (the repo's queue is held); **Approved, not delivered** / **Not ready: not delivered: <R1 reason>** (approved, or not); **Not ready: CI red: <failing checks>** / **Not ready: CI running**; **Not ready: held by a pre-merge gate**; **Not ready: based on <branch>, not <default>**; **Approval voided by a push at <sha>: re-label once Ready for approval**; **Not ready: conflicting: <paths>** (unapproved only: an approved entry's conflict is the queue's to find and eject); **Ready for approval** (no valid approval); **Approved, merges next** / **Approved, queued behind <entry>**. Merge state (clean, behind, conflicting) never changes `admits`.
R6. Beneath the verdict the card lists the facts it came from: Delivered (yes, or the R1 reason), CI (green, red with failing checks, running, at the head), Merge (clean, behind, conflicting with paths, unknown), Approval (none, recorded at this head, voided by a push at <sha>, held unreadable), Whose move (the session, working or idle for N minutes; the driver; or the operator) and Next action with a link (the PR, its checks tab, or the pane focus command).
R7. Every batch PR card on the Batches page leads with its verdict.
R8. Close-out, archive and export PRs shown on the Batches page carry a verdict and facts from the same function family the queue admits them by. Their trust rule takes the place of Delivered: admitted, or the reason the rule refused them.
R9. `fr isolation gc` never reaps a workspace whose run cursor in the worktree has a step or unit in state `running`, nor one whose cursor cannot be read, even when its PR merged (merged or merged-by-content, dry run included). It reports the workspace kept, naming the run and the step. `fr isolation down` is unchanged.
R10. A shipped `fr-debugging` workflow manifest gives a debug run a cursor: `debug`, then `review`, then `deliver`. The fr-debugging skill starts it (`fr run start fr-debugging --branch <fix-branch>`) and resolves each step with a step record, so a debug PR's head carries a cursor whose `deliver` the driver reads (R1). When fr-debugging reuses a workspace that already has a run, it starts no run: the fix rides that run. The skill checks for that run itself, because `fr run start` refuses only a second run of the same workflow on a branch.
R11. In the `fr-debugging` shape the run names its debug journal: the `debug` record emits `debug: <debug-journal path>`, and record entries, the review evidence target, the derived `findings` gate, the PR body and deliver's leftovers gate all read that journal. `review` owes a dispatched reviewer's `kind: review` entry there (evidence `review`, `reviewer`, derived `findings`; finding ids `d-r<k>`). `deliver` owes `tests`, `docs` and `settle`, nothing that needs a plan. Stations and staffing stay with super-fr#1655.
R12. A batch PR whose head can never carry a cursor (one opened before this change, by a flow with no run) is held with Next action "merge it by hand after review, or deliver it through a run", so the hold is visible and never silent.

## Design

### A. Facts carry the cursor's read status (R1)

`PullRequest` gains `cursor_read: "read" | "unread" | "no-clone" | None` beside `cursor`
(None: never asked). `read_cursor` returns every cursor naming the branch and tells "read,
none found" from "could not read"; the stored position folds them (R1: delivered only when
all are). The head it was read at is `PullRequest.head_oid`, which the driver compares with
its live `pr_view` head. `FACTS_SCHEMA` moves 16 → 17 (`FACTS_READS` keeps 3–16).

### B. Readiness — one pure function (R1–R6)

A new module `fr/triage/readiness.py`, pure (no git, no forge, no clock read):

- `Delivered` — the R1 states.
- `Readiness` — the verdict kind and reason (R5), the facts (R6) and `admits`.
- `batch_readiness(batch, qs) -> Readiness` over `QueueSnapshot`, which gains
  `cursors: Mapping[batch id, (head, CursorPosition | None, read status)]`. The driver
  `Snapshot` gains the same map, filled by both of its builders (the command's and
  `views.drive_snapshot`), and `queue_snapshot` copies it.
- `wave_queue._ready` returns `batch_readiness(batch, qs).admits`. `admits` keeps today's
  conditions and adds delivered, nothing else (R5: merge state is a fact).
- `batch_drive._member_reports` calls `batch_readiness` on
  `queue_snapshot(snap, repo, …)`, so the driver and the queue read one input path. An
  approved PR that is not delivered is *awaiting* with "approved, not delivered", never a
  member (R2). The only `pr_ready` calls (`triage_batch_cmd._queue_entry`) and the only
  `pr_merge` (`queue_exec`) are reached through queue admission alone.
- `QueuePlan.readiness` carries the verdict of every batch and other entry of its repo;
  "merges next" / "queued behind" come from the plan's own entry order.
- The voiding sha (R3) is `ApprovalEvent.voided_at` of the PR's last approval event in
  `batch.events` after settlement, or the live head while the verdict is still `Void`.
  (`approval.voided_at()` returns the approved head and is not used for it.)

### C. The Batches page (R4–R8, R12)

`kanban.build_board` takes the readiness map from the plan it already builds, and
`kanban_render` leads each batch PR card with the verdict and lists the facts beneath it.
The board's `LivePr` (`views.drive_snapshot`) gains `mergeable`/`merge_state` from
`PullRequest`. A repo whose queue is held gets R5's first verdict. A test feeds the board
and the queue one snapshot and asserts equal verdicts and equal `admits`.

Other entries (R8): `drive_pass` keeps, beside the `Admitted` entries, the candidates a
trust rule refused with their reason; `QueueSnapshot.refused` carries them.
`other_readiness(key, qs)` reads both and is what `_other_ready` returns `.admits` of.

### D. gc keeps a running run (R9)

In `isolation/local.py`, `_reap_or_classify` (both the dry-run and live paths, for the
`merged` and `merged-by-content` verdicts) first reads the worktree's cursors with
`preserve.branch_runs` and a new `running` predicate over steps and units (its `active`
flag also covers `pending`/`blocked`, which reap as today). A running or unreadable cursor
keeps the workspace with `kept: run <id> step <step> is running`. `_reap_hazard` and
`_down_worktree_tail`, which `down` shares, are untouched. External gc never reaps and
needs no change.

### E. A minimal fr-debugging shape (R10, R11)

`plugins/super-fr/workflows/fr-debugging.yaml` (and its wheel copy), `unit: run`:

- `debug` — `kind: agent`, skill `super-fr:fr-debugging`, `emits: [debug, journal:debug]`.
  `debug` is a new emitted artifact token (a path that must exist, like `spec`/`plan`).
- `review` — `kind: agent`, the requesting/receiving code-review skills,
  `needs: [debug]`, `emits: [journal:debug]`, `evidence: [review, reviewer, findings]`.
- `deliver` — `kind: agent`, `needs: [debug]`, `emits: [pr]`,
  `evidence: [tests, docs, settle]`.

Readers of the debug journal: `record/apply.py`'s slug resolution (scope `debug`, from the
emitted `debug` path), `_EvidenceTarget` (`scope="debug"`), the review-entry lookup and the
derived `findings` gate, and `record/pr_body._journals`/`unaccounted`. It passes
`fr workflow check`. The skill's §0 starts the run instead of a bare `fr isolation up`
(reuse case: no new run, R10), and §3–§4 resolve `debug`, `review` and `deliver` with step
records. super-fr#1655 is referenced, not closed.

### Out of scope

Stations, staffing and the other ad-hoc flows (super-fr#1655); changing the approval rule
(decision d2); the gc rule for `down`; check-run job URLs in facts (R6 links the PR's
checks tab).

## Verification

strategy: candidate
gate: reviewer

- batch-merge-needs-deliver: none — CI unit tests over the pure readiness function and `plan_queue`/member snapshots: an approved green draft with `deliver: running` is neither readied nor admitted
- batch-readiness-verdict: none — CI unit tests over `build_board`/`kanban_render` with snapshot fixtures for every verdict, and a test that the card's verdict and the queue's admission come from the same call
- batch-readiness-other-entries: none — CI unit tests over close-out, archive and export entries' verdicts
- gc-keeps-running-run: none — CI unit tests over the gc reap verdict with a worktree cursor at `running`
- fr-debugging-run-cursor: none — CI: `fr workflow check` over the shipped manifest, resolve tests for the debug-journal evidence target, and the skill tripwires
- batch-readiness-no-cursor-hold: none — CI unit tests over the readiness function for each R1 reason and the R12 next action
- batch-merge-live-drive: live — only a real drive pass over a real draft batch PR shows the hold end to end; the CI suite proves the logic over snapshots (Test Plan 1)

gate: batch-merge-live-drive=reviewer

## Test Plan

1. post-merge — operator-driven: on the next live `fr triage batch drive`, an approved, green batch PR whose run is not at `deliver: done` stays on the Batches page as "Approved, not delivered" and is neither marked ready nor merged; once its run delivers and the operator re-labels, it merges.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-24-batch-merge-readiness | `derio-net/super-fr` | `2026-11-24-batch-merge-readiness` | — |
