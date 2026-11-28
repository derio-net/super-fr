# Pass a post-merge gate whose rows are walked, for PRs outside a batch

Issue: derio-net/super-fr#1764 (triage batch `tester-gate-auto-pass`).

## Background

A merged PR that carries `gate:tester` (or `gate:devops`) without the `-passed` label holds
a post-merge gate. The triage board lists every such PR in a collected repo in its Needs
you · Tester or · DevOps lane (spec `2026-11-01-gate-backfill` R13). A PR a batch delivered
reaches the lane through its batch (`fr.triage.lanes.lane_of`). Any other PR reaches it
through `facts.gated_prs` and `lanes.unlisted_gated_prs`, and its card is built by
`lanes.gated_pr_lane` (`packages/fr/src/fr/triage/lanes.py:68`), which reads labels only.

The gate passes in two ways:

1. explicitly, with `fr gate pass` (`commands/gate_cmd.py:303`);
2. automatically, by the wave driver, once every acceptance row the gate holds reads
   `walked` on the default branch (spec `2026-10-14-exit-gates` R14).

Route 2 runs only over batches. `Driver._ledgers` (`commands/triage_batch_cmd.py:4762`)
builds a `GateLedger` for each landed batch and reads its gated rows with
`fr.triage.ledger.gated_rows_at`, keyed on the batch's branch. `drive_pass` calls
`_gate_actions` (`triage/batch_drive.py:1222`) only for a gated batch
(`batch_drive.py:1535`). That function plans `awaiting-live` labels and the `gate-pass`.
A PR outside a batch never gets a ledger, so walking its rows never moves its card. Yet
the card's hint (`lanes.py:83`) still tells the operator to "walk its gated rows". Most
cards in the Needs you · Tester column are such PRs whose rows are already walked.

`gated_rows_at` needs only a checkout, the default branch's tip and a branch name. It
finds the run cursor naming that branch, live or archived (gh#1399), and folds the exit.
A merged PR's `head_ref` is that branch. So the read the batch path makes works unchanged
for a PR outside a batch, provided an fr run delivered it.

## Requirements

R1. A wave-driver pass over the whole scope (no `--batch` selection) treats each loose gated PR the same way it treats a gated landed batch. A loose gated PR is a merged PR in `facts.gated_prs` that is not the merged PR of a batch with no close-out event. The pass reads the rows that the PR's held gates hold on the repo's default branch, through the run cursor that delivered the PR, and plans a `gate-pass` for each held gate whose rows all read `walked`.
R2. The rules of the batch route hold unchanged for these PRs. Walked rows never pass a run-level gate that no row inherits, and never pass a `devops` gate that the plan's ops promoted. A held gate with no row passes only through `fr gate pass`.
R3. The pass labels each open issue that those rows cite `fr:awaiting-live` when it lacks the label. It does this at most once per issue per pass, across batches and loose PRs together.
R4. Executing such a `gate-pass` does what a batch's does. It swaps `gate:<g>` for `gate:<g>-passed` on the merged PR, comments why (when comments are on), and closes the PR's fr-owned owed trackers for that gate (gate-backfill R12), under the same forge-ledger settings.
R5. The cursor that delivered a loose PR is the one cursor, live or archived, on the default branch whose `branch` is the PR's head branch. When that cursor records a `pr`, it must name this PR's number. No cursor means no rows, and nothing is passed or labelled. A cursor whose `pr` names another PR also means no rows. More than one cursor naming the branch makes the rows unreadable.
R6. When a loose PR's rows cannot be read, the driver reports it once, as it does for a batch, and plans nothing for that PR. A failed forge write is reported, makes `--once` exit 1, and is planned again on the next pass.
R7. A drive narrowed with `--batch` plans nothing for loose PRs.
R8. A batch with a close-out event whose merged PR still holds a gate is a loose PR under R1. The batch route skips every closed-out batch (`batch_drive.py:1484`, `_ledgers`), and the board already lists its PR outside its batch (`lanes.unlisted_gated_prs`).
R9. The board keeps listing these PRs as before. A card leaves its lane when the next collect reads the passed label.

## Design shape

```
packages/fr/src/fr/triage/
  batch_drive_types.py ~ + GatedRow, GateLedger (moved from batch_drive, re-exported there)
                       + LooseLedger(repo, number, head_ref, ledger: GateLedger)
                       ~ Action: + repo: str = ""        # set when batch == "" (a loose PR)
  pr_gates.py          + NEW, pure, imports only batch_drive_types and fr.labels:
                         gate_actions(owner, repo, ledger, awaiting_unlabelled, labelled) -> [Action]
                         loose_prs(facts, batches) -> [LooseLedger]   # R1, R8; rows None
  batch_drive.py       ~ _gate_actions -> pr_gates.gate_actions(batch.id, "", ...)
                       ~ Snapshot: + loose_ledgers: tuple[LooseLedger, ...] = ()
                       ~ drive_pass: after the batches loop, each loose ledger with rows read
                         -> pr_gates.gate_actions("", repo, ...), sharing `labelled`   # R1-R3
  ledger.py            ~ gated_rows_at(checkout, ref, branch, *, pr: int | None = None)
                         _run_text: with pr, refuse >1 cursor on the branch, and no rows
                         when the cursor's `pr` names another number                  # R5
packages/fr/src/fr/commands/
  triage_batch_cmd.py  ~ _gated_rows(repo, branch, label, pr=None)   # was (repo, batch)
                       ~ Snapshot(...): loose_ledgers=loose_ledgers(self, ...) when no --batch
                       ~ _act: a loose awaiting-live / gate-pass runs before the batch lookup
  triage_drive_loose.py + NEW: loose_ledgers(driver, facts, judgements, unread): fills rows
                         through driver._gated_rows                                   # R6, R7
```

## Design

### Types

`GatedRow` and `GateLedger` move from `batch_drive.py` to `batch_drive_types.py`, beside
`Action`. `batch_drive` re-exports both, so `ledger.py`, `lanes.py` and the tests keep
their imports. `LooseLedger(repo, number, head_ref, ledger)` is new there. This keeps
`pr_gates` free of `batch_drive`, which calls it, so the two never import each other.

### Planning (pure)

`fr.triage.pr_gates.gate_actions(owner, repo, ledger, awaiting_unlabelled, labelled)` holds
the body of today's `_gate_actions`. *owner* becomes the action's `batch`: the batch id, or
`""` for a loose PR, in which case each action also carries `repo`. `batch_drive._gate_actions`
calls it with the batch id, so both routes share one rule (R2).

`pr_gates.loose_prs(facts, batches)` returns a `LooseLedger` for each PR of `facts.gated_prs`
whose `(repo, number)` is not the merged PR (`batch_pr`) of a batch without a close-out
event (R1, R8). Its `ledger` is `GateLedger(pr, frozenset(labels))` with `rows` None.

`Snapshot.loose_ledgers` defaults to empty. After the batches loop, `drive_pass` calls
`gate_actions("", l.repo, l.ledger, ...)` for each loose ledger whose `rows` were read. It
shares the pass's `labelled` set (R3). A ledger whose `rows` is None plans nothing.

### Reads (the command)

`Driver._gated_rows(repo, branch, label, pr=None)` replaces `(repo, batch)`. The batch
caller passes `recorded_branch(batch)` and the batch id as *label*. The cache key becomes
`(repo, tip, branch, pr)`, and the warning names *label*. The report stays
`_report_once`, so it is printed once per drive process for each read and error (R6).

`triage_drive_loose.loose_ledgers(driver, facts, judgements, unread)` is called only when
the drive has no `--batch` selection (R7). For each `pr_gates.loose_prs` entry in a repo
that is not unread, it calls `driver._gated_rows(repo, head_ref, f"PR #{n}", pr=n)` and
copies `rows`, `run_gate`, `run_gate_inherited` and `ops_promoted` into the ledger.

`ledger.gated_rows_at` gains `pr`. With `pr` set, `_run_text` collects every cursor naming
the branch. More than one raises `TriageError` (unreadable, R6). One whose `pr` url does
not end in `/<number>` returns `NO_RUN`. No cursor also returns `NO_RUN` (R5). A batch
read passes no `pr` and behaves as today.

### Execution

`_act` looks up the action's batch before it reaches `awaiting-live` and `gate-pass`. An
action with `batch == ""` and `repo` set is dispatched before that lookup, to the existing
`_label_awaiting` and `_pass_gate` with `action.repo`. Both already work from the action
alone, so R4 needs no new writer. A claim never holds a loose action, because
`_held_now` holds only batch ids.

`triage_batch_cmd.py` sits 4 lines under its line budget
(`tests/unit/test_tripwire_module_budget.py`). The `_gated_rows` signature change, the
`Snapshot` argument and the `_act` branch go there, and the reads go in
`triage_drive_loose.py`. The edits there must stay within the budget, or the budget
moves in the same diff with its reason.

### What does not change

The board (`lanes.py`, `kanban.py`, `views.py`) is untouched: it reads facts only. For
a PR whose branch an fr run's cursor names, the hint "walk its gated rows" is now true.
For a gated PR that no fr run delivered (a gate-backfill adoption or a hand-labelled PR),
walking rows still cannot pass the gate, and the hint stays wrong. That case is left open
and filed as a follow-up: a fix needs a facts-level signal of whether a cursor exists.
`fr gate pass` is untouched. No artifact shape changes, because `Snapshot`, `Action` and
the ledgers are in-memory values.

## Verification

strategy: candidate
gate: developer
settle.conflicts: report — batch tester-gate-auto-pass: the wave driver owns this PR's mergeability
settle.ci: report — batch tester-gate-auto-pass: the wave driver owns this PR's CI

- loose-gated-pr-rows-walked-pass: none — unit tests drive `drive_pass` and the driver's executor with a fake forge and a fixture default branch
- loose-gated-pr-awaiting-live: none — unit tests drive `drive_pass` over batches and loose PRs citing the same issue
- loose-gated-pr-no-pass-without-evidence: none — unit tests cover a PR with no run cursor, a cursor naming another PR, two cursors on one branch, unreadable rows, a narrowed drive and a failed write
- loose-gated-pr-batch-guards: none — unit tests drive `drive_pass` over loose PRs whose gate is a run gate no row inherits, an ops-promoted devops gate, or a held gate with no rows
- closed-out-batch-gated-pr-pass: none — unit tests drive `drive_pass` over a closed-out batch whose merged PR holds a walked tester gate

The run's `candidate` walk installs the branch into a throwaway prefix and smokes it. Each
row is proven by the CI tests named on its line. None needs a released build, so there is
no Test Plan.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-28-tester-gate-auto-pass | `derio-net/super-fr` | `2026-11-28-tester-gate-auto-pass` | — |
