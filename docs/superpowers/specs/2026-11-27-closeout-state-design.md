# Close-outs and batches never stuck as started or Running

Batch `closeout-state`: super-fr#1601 and super-fr#1626, one pull request.

## Background

Two defects leave the wave driver's state saying something that is not true.

**#1601 — a failing take-back hides the dispatch error.** The collected close-out start,
`_Driver._collected_close_out` (`packages/fr/src/fr/commands/triage_batch_cmd.py:7481`),
records its start marker before the runner opens the session (gh#883), then calls
`runner.dispatch` (`:7553`). When the dispatch raises, the `except` block takes the marker
back with `save_closeouts(path, read, read=[*read, marker])` (`:7555`) with no guard of its
own. If that write raises too (a `TriageError` from the compare-and-swap read, or the
`fail_exit` that `fr.commands.triage_cmd.fail` raises, `triage_cmd.py:109`), the dispatch
error survives only as `__context__`: the pass boundary reports the write's error, and the
marker stays recorded, so `_collected_under_way` (`fr/triage/batch_drive.py:865`) holds every
later close-out of that repo until the `closeout-abandoned` rule (`batch_drive.py:1117`,
`STALE_CLOSEOUT` 15 minutes, `:88`) re-owes it. The per-batch start, `_Driver._close_out`
(`triage_batch_cmd.py:7399`), has the same shape: its take-back
`_write(self.target, judgements.batches, ...)` (`:7470`) also sits unguarded after a failed
`runner.dispatch` (`:7467`). The pure pass now plans that start only as `recorded=True`
(`batch_drive.py:1896`), so its dispatch branch is reachable only through older planning;
it is fixed the same way so the two never drift.

`_Driver._dispatch_failed` (`triage_batch_cmd.py:7676`) is the one place a failed dispatch is
reported: once per batch and cause, `failed_write` set so `--once` exits 1, retried next pass.

**#1626 — a batch whose repo left the scope reads as Running.** `derive_batch_stage`
(`fr/triage/batch.py:345`) finds the batch PR through `batch_pr`; when the batch's repo is no
longer in `facts.repos`, no PR is found and the stage falls through to `dispatched`
(`batch.py:353-354`), which the board maps to the Running column (`fr/triage/kanban.py:117`).
`facts.repos` is the whole scope, skipped repos included (`fr/triage/model.py:713-716`), so a
repo missing from it has left the scope, not merely failed to read. Every verb that needs the
repo then refuses through `batch_repo` (`batch.py:110`) returning `None`: `batch cancel`
(`triage_batch_cmd.py:1106`), `batch dispatch --repair` (`:2200`), `batch replace --repair`
(`:1848`), `batch adopt` (`:2481`) and `batch focus` (`commands/triage_kanban_cmd.py:203`).
`batch list` shows the close-out column from the events alone (`closeout_state`,
`batch.py:436`), so it says `archived` while the board says Running.

Docs currency: `docs/explainers/fr-triage.md` covers `triage/**` and names the batch stages;
`docs/reference/cli.md` covers `commands/*.py` and holds the generated command tree, which a new
`--orphaned` option's help does not change (the tree lists commands, not options).

## Requirements

R1. When a close-out's `runner.dispatch` fails and the take-back of its start record then fails
too, both in the collected start and in the per-batch start, the driver reports one line naming
the dispatch error and the take-back error, and the pass continues.
R2. That failure is reported as a failed dispatch is today: once per batch and cause, the pass
counted as a failed write so `drive --once` exits 1, and the close-out retried on a later pass.
The driver is not stopped.
R3. A take-back that succeeds behaves exactly as today.
R4. A batch whose repo is not in the scope's facts has the derived stage `left-scope`, never
stored, unless its last lifecycle event is a cancel (then it stays `cancelled`). If the repo
returns to the scope, the batch derives its old stage again.
R5. A `left-scope` batch is closed out: it holds no issue's open-batch membership, the driver
plans no action for it and asks for no checkout of its repo, and it holds no wave open.
R6. The board draws a `left-scope` batch in the Done column with a `repo left this scope` pill
and offers no Jump command for it; `batch list` shows its stage as `left-scope`.
R7. `fr triage batch focus` on a `left-scope` batch refuses with a message that says its repo
left the scope and names `fr triage batch cancel <id> --orphaned`.
R8. `fr triage batch cancel <id> --orphaned` retires a `left-scope` batch: it appends only the
cancel event (no label, comment or claim write, and no checkout), and its plan says the repo
left the scope so nothing on the forge is withdrawn. `cancel` without `--orphaned` on a
`left-scope` batch refuses and names the flag; `--orphaned` on any other batch refuses.

## Design

### #1601 — the take-back has its own guard (R1-R3)

```python
try:
    handle = runner.dispatch(item)
except Exception as exc:
    message = f"runner `{launch.runner}` failed to dispatch {item.id}: {exc}"
    try:
        save_closeouts(path, read, read=[*read, marker])     # the take-back
    except Exception as back:                                 # noqa: BLE001
        message += f"; taking back its start record failed too: {_error_text(back)}"
    return self._dispatch_failed(members[0], message, exc), False
```

`_close_out` takes the same shape around its `_write`. `_error_text` reads the message a
`fail_exit` carries (its `str()` is the exit code, per `triage_cmd.fail`'s docstring), else
`str(exc)`. The cause key `_dispatch_failed` dedupes on stays the dispatch error's, so a take-back
that keeps failing is said once. Nothing else changes: the marker that stayed is re-owed by the
existing `closeout-abandoned` rule.

### #1626 — `left-scope` (R4-R8)

- `fr/triage/batch.py`: `BatchStage` and `BATCH_STAGES` gain `left-scope`; `CLOSED_OUT` holds it.
  `derive_batch_stage` returns it after the cancel check and before `batch_pr` when
  `batch_repo(batch, facts)` is `None`.
- `fr/triage/kanban.py`: `_COLUMN_OF_STAGE["left-scope"] = "done"`, `PILL_STAGES` holds it with the
  pill text `repo left this scope`; the card's Jump is omitted for it.
- Every reader that enumerates stages (`views.py`, `batch_drive.py`, `lanes.py`, `render.py`,
  `snapshot.py`, `check.py`, `readiness.py`, `claim_sync.py`) is checked for a closed set that must
  name the new stage; a wave of only finished or `left-scope` batches is finished.
- `commands/triage_kanban_cmd.py` `batch_focus_command`: the R7 refusal before the `batch_repo`
  check.
- `commands/triage_batch_cmd.py` `batch_cancel_command`: a `--orphaned` flag; the R8 checks come
  before the `CLOSED_OUT` refusal and the `batch_repo` refusal; with it, the plan prints one line and
  `--yes` appends the cancel event through `_write`.

## Design shape

```text
packages/fr/src/fr/
├── commands/
│   ├── triage_batch_cmd.py
│   │   ├── _Driver._collected_close_out   ~ take-back wrapped; one line, both errors (R1-R3)
│   │   ├── _Driver._close_out             ~ the same for the per-batch start
│   │   └── batch_cancel_command           ~ --orphaned retires a left-scope batch (R8)
│   └── triage_kanban_cmd.py
│       └── batch_focus_command            ~ left-scope refusal naming cancel --orphaned (R7)
└── triage/
    ├── batch.py
    │   ├── BatchStage / CLOSED_OUT        + "left-scope"
    │   └── derive_batch_stage             ~ cancel > left-scope > PR-derived (R4, R5)
    └── kanban.py                          ~ left-scope -> Done + pill, no Jump (R6)

derive_batch_stage(batch, facts):
    no lifecycle events      -> obsolete | proposed      (repo present)
    last event is cancel     -> cancelled
    repo not in facts.repos  -> left-scope               (new)
    no PR / open / closed    -> dispatched | pr-open | abandoned
    merged                   -> merged | partial
```

## Verification

strategy: none

- closeout-takeback-both-errors: none — unit tests drive both close-out starts with a runner whose dispatch raises and a store whose write raises, in CI
- batch-left-scope-stage: none — unit tests over `derive_batch_stage`, the pure pass and the board render with a facts file lacking the repo, in CI
- batch-left-scope-cancel: none — unit tests of `batch focus` and `batch cancel --orphaned` against a state directory whose facts lack the repo, in CI

## Out of scope

- Collect appending a stored `repo_left_scope` event (judgements schema 15): the stage is derived.
- Stopping the driver on a failed take-back.
- `fr triage check` listing left-scope batches.
