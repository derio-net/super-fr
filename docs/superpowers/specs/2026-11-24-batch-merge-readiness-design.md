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

R1. A batch PR is **delivered** only when a run cursor at the PR's current head names the PR's branch and records `deliver` done. No cursor naming the branch, a cursor read at a different head than the live one, or a head the driver could not read is not delivered, and the reason says which.
R2. The wave driver never marks a batch PR ready, never admits it to the merge queue and never merges it while it is not delivered, whatever its approval, draft state and checks. An approved green PR that is not delivered is held as "approved, not delivered".
R3. Approval keeps its current rule (pinned to the PR's content). A push after an approval that changes the diff, the `deliver` resolve's own commit included, voids it, and the page says so and says to re-label once the PR reads Ready for approval.
R4. One pure function decides a batch PR's readiness. The queue's admission of a batch entry, the driver's member classification and the Batches page all read it, so the page can never call a PR ready that the driver would refuse, or the reverse.
R5. The verdict is exactly one of: **Ready for approval** (delivered, CI green at the head, mergeable, no valid approval yet); **Not ready: <reason>** (not delivered — the run and its cursor step, or no run cursor at the head; CI red, naming the failing checks; CI running; conflicting, naming the paths when known; behind; based on another branch; held by a pre-merge gate); **Approved, merges next**; **Approved, queued behind <entry>**; **Approved, not delivered**; **Approval voided by a push at <sha>: re-label once Ready for approval**.
R6. Beneath the verdict the card lists the facts it came from: Delivered (yes, or the run and step, or no cursor at the head), CI (green, red with failing checks, running, at the head), Merge (clean, behind, conflicting with paths), Approval (none, recorded at this head, voided by a push at <sha>, held unreadable), Whose move (the session — working, or idle for N minutes —, the driver, or the operator) and Next action with a link (the PR, the pane focus command, or the failing job).
R7. Every batch PR card on the Batches page leads with its verdict.
R8. Close-out, archive and export PRs shown on the Batches page carry a verdict and facts from the same function family the queue admits them by; their trust rule takes the place of Delivered.
R9. `fr isolation gc` never reaps a workspace whose run cursor in the worktree has a step or unit in state `running`, even when its PR merged; it reports the workspace kept, naming the run and the step. `fr isolation down` is unchanged.
R10. A shipped `fr-debugging` workflow manifest gives a debug run a cursor: `debug` → `review` → `deliver`. The fr-debugging skill starts it (`fr run start fr-debugging --branch <fix-branch>`) and resolves each step with a step record, so a debug PR's head carries a cursor whose `deliver` the driver reads (R1).
R11. In the `fr-debugging` shape, `review` owes a dispatched reviewer's `kind: review` entry in the debug journal (evidence `review`, `reviewer`, derived `findings`, as `spec-review` owes in the spec journal), and `deliver` owes the evidence that needs no plan: `tests`, `docs` and `settle`. Stations and staffing stay with super-fr#1655.

## Design

### A. Readiness — one pure function (R1, R4–R6)

A new module `fr/triage/readiness.py`, pure (no git, no forge, no clock read), beside
`wave_queue.py`:

- `Delivered` — `delivered` | `not-delivered(run, step)` | `no-cursor` | `unread`,
  computed from the cursor position collect stored for the PR **and the head it was read
  at**, compared with the live head. Only `delivered` passes (R1).
- `Readiness` — the verdict kind (R5), its one-line reason, and the facts (R6):
  `delivered`, `ci` (+ failing names), `merge` (+ paths), `approval` (+ voiding sha),
  `whose_move`, `next_action` (+ link).
- `batch_readiness(batch, qs) -> Readiness` over the existing `QueueSnapshot`, which
  gains the per-batch cursor (`cursors: Mapping[batch id, (head, CursorPosition | None)]`).
  `Readiness.admits` is the merge-admission boolean.
- `wave_queue._ready` becomes `batch_readiness(batch, qs).admits`; the order and queue
  position stay `plan_queue`'s. `QueuePlan` carries `readiness` for every batch and other
  entry of its repo, so "merges next" / "queued behind" come from the plan that also
  decides the merge.
- The driver's member classification (`batch_drive.py` `_queue_members`) reads the same
  verdict: an approved PR that is not delivered is *awaiting* with reason
  "approved, not delivered", never a member and never readied (R2).

The cursor at a head never changes, so the driver's existing per-head cache
(`triage_batch_cmd.py` `cursor_at`) keeps reads to one per head per process.

### B. Driver (R2, R3)

Every path that marks a batch PR ready or lands it — the queue's admission and any
`gh pr ready` the executor issues — is gated on `Readiness.admits`. Approval settlement is
unchanged (R3): `settle_approvals` still voids on a content change, and the verdict reads
the voiding head from the verdict it already returns.

### C. The Batches page (R5–R8)

`kanban.build_board` takes the readiness map from the plan it already builds (one plan per
board), and `kanban_render` renders the verdict first on every batch PR card, the facts
beneath it, and a verdict line for each close-out, archive and export PR it shows. For a
repo whose queue is held (`queue-held`), the verdict is Not ready with the hold's reason.
The page reads no extra source: everything comes from facts and the pass plan.

Other entries (R8): `other_readiness(entry, qs)` returns the same `Readiness` shape, with
Delivered replaced by the trust rule that admitted it (or why it did not), and is what
`_other_ready` returns `.admits` of.

### D. gc keeps a running run (R9)

The local and external `gc` reap verdict for a merged PR first reads the run cursor in the
workspace's worktree (the `docs/superpowers/runs/*.yaml` naming its branch, under the
workspace's placement). A step or unit in state `running` keeps the workspace with a
`kept: run <id> step <step> is running` line; an unreadable cursor keeps it too (unknown
is not idle). No cursor naming the branch reaps as today.

### E. A minimal fr-debugging shape (R10, R11)

`plugins/super-fr/workflows/fr-debugging.yaml` (and its wheel copy), `unit: run`:

- `debug` — `kind: agent`, skill `super-fr:fr-debugging`, `emits: [journal:debug]`.
- `review` — `kind: agent`, the requesting/receiving code-review skills,
  `emits: [journal:debug]`, `evidence: [review, reviewer, findings]`, its evidence target
  the debug journal (a new `_evidence_target` case beside the spec journal's).
- `deliver` — `kind: agent`, `emits: [pr]`, `evidence: [tests, docs, settle]`.

It passes `fr workflow check`. The skill's §0 starts the run instead of a bare
`fr isolation up` (the same workspace rules apply, `fr run start` enters isolation), and
§3–§4 resolve `debug`, `review` and `deliver` with step records. The debug journal stays
the record; the cursor is the gate the driver reads. super-fr#1655 is referenced, not
closed.

### Out of scope

Stations, staffing and the other ad-hoc flows (super-fr#1655); changing the approval rule
(decision d2); the gc rule for `down`.

## Verification

strategy: candidate
gate: reviewer

- batch-merge-needs-deliver: none — CI unit tests over the pure readiness function and `plan_queue`/member snapshots: an approved green draft with `deliver: running` is neither readied nor admitted
- batch-readiness-verdict: none — CI unit tests over `build_board`/`kanban_render` with snapshot fixtures for every verdict, and a test that the card's verdict and the queue's admission come from the same call
- batch-readiness-other-entries: none — CI unit tests over close-out, archive and export entries' verdicts
- gc-keeps-running-run: none — CI unit tests over the gc reap verdict with a worktree cursor at `running`
- fr-debugging-run-cursor: none — CI: `fr workflow check` over the shipped manifest, resolve tests for the debug-journal evidence target, and the skill tripwires
- batch-merge-live-drive: live — only a real drive pass over a real draft batch PR shows the hold end to end; the CI suite proves the logic over snapshots (Test Plan 1)

gate: batch-merge-live-drive=reviewer

## Test Plan

1. post-merge — operator-driven: on the next live `fr triage batch drive`, an approved, green batch PR whose run is not at `deliver: done` stays on the Batches page as "Approved, not delivered" and is neither marked ready nor merged; once its run delivers and the operator re-labels, it merges.
