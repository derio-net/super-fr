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

R1. A wave-driver pass over the whole scope (no `--batch` selection) treats each merged PR in `facts.gated_prs` that no batch of the state file delivered the same way it treats a gated landed batch: it reads the rows the PR's held gates hold on the repo's default branch, keyed on the PR's head branch, and plans a `gate-pass` for each held gate whose rows all read `walked`.
R2. The rules of the batch route hold unchanged for these PRs: a run-level gate that no row inherits is never passed by walked rows, a `devops` gate promoted by the plan's ops is never passed by walked rows, and a gate with no row passes only through `fr gate pass`.
R3. The pass labels each open issue that those rows cite `fr:awaiting-live` when it lacks the label, at most once per issue per pass, across batches and these PRs together.
R4. Executing such a `gate-pass` does what a batch's does: it swaps `gate:<g>` for `gate:<g>-passed` on the merged PR, comments why (when comments are on), and closes the PR's fr-owned owed trackers for that gate (gate-backfill R12), under the same forge-ledger settings.
R5. A PR whose head branch no run cursor names on the default branch has no rows, and nothing is passed or labelled for it. A PR whose rows cannot be read is reported once per pass and nothing is planned for it. A failed forge write is reported, makes `--once` exit 1, and is planned again on the next pass.
R6. A drive narrowed with `--batch` plans nothing for PRs outside a batch.
R7. The board keeps listing these PRs as before; a card leaves its lane when the next collect reads the passed label.

## Design shape

```
packages/fr/src/fr/triage/
  pr_gates.py          + NEW, pure: the gate actions of one ledger, batch or not
                         gate_actions(owner, ledger, awaiting_unlabelled, labelled) -> [Action]
                         loose_ledgers(facts, batches) -> [(repo, GateLedger)]   # R1, R6 input
  batch_drive.py       ~ _gate_actions -> pr_gates.gate_actions(batch.id, ...)
                       ~ drive_pass: after the batches, for each snap.loose_ledgers entry
                         with rows read -> pr_gates.gate_actions(...)           # R1-R3
                       ~ Snapshot: + loose_ledgers: tuple[LooseLedger, ...] = ()
  batch_drive_types.py ~ Action: + repo: str = ""   # set when batch == "" (a loose PR)
packages/fr/src/fr/commands/
  triage_batch_cmd.py  ~ Snapshot(...): loose_ledgers=self._loose_ledgers(...) when no --batch
                       ~ _act: a loose awaiting-live / gate-pass runs before the batch lookup,
                         on action.repo                                         # R4, R5
  triage_drive_loose.py + NEW (if the budget needs it): _loose_ledgers' reads through
                         the existing _gated_rows cache
```

## Design

### Planning (pure)

`fr.triage.pr_gates` holds the body of today's `_gate_actions`, keyed on a ledger rather
than a batch. Its owner argument is the action's `batch` (the batch id, or `""` for a PR
outside a batch); for `""` it also sets `Action.repo`. `batch_drive._gate_actions` becomes
a call to it, so the two routes share one rule (R2).

`loose_ledgers(facts, batches)` returns each PR of `facts.gated_prs` whose `(repo,
number)` is not the merged PR of any batch in the state file (`batch_pr`), as a
`LooseLedger(repo, head_ref, GateLedger(pr, labels))`. A batch's PR keeps going through
its batch, even when the batch is closed out, because its ledger and close-out are the
batch's.

`Snapshot` gains `loose_ledgers`, default empty. `drive_pass`, after the batches loop,
calls `gate_actions` for each loose ledger whose `rows` were read, sharing the pass's
`labelled` set (R3). Those with `rows is None` plan nothing.

### Reads (the command)

The command fills `loose_ledgers` only when the drive is not narrowed by `--batch` (R6).
For each loose PR in a repo it could read, it calls the same `_gated_rows` read and cache
that batches use, keyed on `(repo, tip, head_ref)`, and copies `rows`, `run_gate`,
`run_gate_inherited` and `ops_promoted` into the ledger. A `TriageError` is reported once
with the PR's number and leaves `rows` None (R5). `gated_rows_at` returns `NO_RUN` (no
rows) when no cursor names the branch, so such a PR plans nothing (R5).

### Execution

`_act` looks up the action's batch before it reaches `awaiting-live` and `gate-pass`. An
action with `batch == ""` and `repo` set is dispatched before that lookup, to the existing
`_label_awaiting` and `_pass_gate` with `action.repo`. Both already work from the action
alone, so R4 needs no new writer. A loose action is never held by a claim (`_held_now`
holds batch ids).

`triage_batch_cmd.py` sits 4 lines under its line budget
(`tests/unit/test_tripwire_module_budget.py`). The new reads go in a new module beside
it, and the edits there stay net neutral or the budget moves in the same diff with its
reason.

### What does not change

The board (`lanes.py`, `kanban.py`, `views.py`) is untouched: it reads facts only, and the
hint is now true for a PR whose branch a run cursor names. `fr gate pass` is untouched.
No artifact shape changes: `Snapshot` and `Action` are in-memory values.

## Verification

strategy: candidate
gate: developer
settle.conflicts: report — batch tester-gate-auto-pass: the wave driver owns this PR's mergeability
settle.ci: report — batch tester-gate-auto-pass: the wave driver owns this PR's CI

- loose-gated-pr-rows-walked-pass: none — unit tests drive `drive_pass` and the driver's executor with a fake forge and a fixture default branch
- loose-gated-pr-awaiting-live: none — unit tests drive `drive_pass` over batches and loose PRs citing the same issue
- loose-gated-pr-no-pass-without-evidence: none — unit tests cover a PR with no run cursor, unreadable rows, a narrowed drive and a failed write

The run's `candidate` walk installs the branch into a throwaway prefix and smokes it. Each
row is proven by the CI tests named on its line. None needs a released build, so there is
no Test Plan.

## Implementation Plans
