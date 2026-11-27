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
repo missing from it has left the scope, except when an org's repo list was cut at its limit
(a `repos` truncation warning, `fr/triage/collect.py:273-280`). Every verb that needs the
repo then refuses through `batch_repo` (`batch.py:110`) returning `None`: `batch cancel`
(`triage_batch_cmd.py:1106`), `batch dispatch --repair` (`:2200`), `batch replace --repair`
(`:1848`), `batch adopt` (`:2481`) and `batch focus` (`commands/triage_kanban_cmd.py:203`).
`batch list` shows the close-out column from the events alone (`closeout_state`,
`batch.py:436`), so it says `archived` while the board says Running. `drive` asks for the
departed repo's checkout before it reads any facts: `build_driver` (`triage_batch_cmd.py:8140`)
names a checkout for every chosen batch's repo.

Docs currency: `docs/explainers/fr-triage.md` covers `triage/**` and names the batch stages;
`docs/reference/cli.md` covers `commands/*.py` and holds the generated command tree, which a new
`--orphaned` option's help does not change (the tree lists commands, not options).

## Requirements

R1. When a close-out's `runner.dispatch` fails and the take-back of its start record then fails
too, both in the collected start and in the per-batch start, the driver reports one line naming
the dispatch error and the take-back error, prints no other line for the take-back, and the pass
continues.
R2. That failure is reported as a failed dispatch is today: once per batch and cause, the pass
counted as a failed write so `drive --once` exits 1. The driver is not stopped. A collected
close-out whose marker stayed is owed again by the existing `closeout-abandoned` rule; a
per-batch close-out event that stayed reads as close-out started (that start is no longer planned
by the pass, so no rule re-owes it).
R3. A take-back that succeeds behaves exactly as today.
R4. A batch has left the scope when its repo is not in the scope's facts and those facts hold no
truncation warning for the repo list. Such a batch has the derived stage `left-scope`, never
stored, whether or not it was ever dispatched, unless its last lifecycle event is a cancel (then
it stays `cancelled`). When the repo list was truncated, the batch keeps the stage it derives
today. If the repo returns to the scope, the batch derives its old stage again.
R5. A `left-scope` batch is closed out: it holds no issue's open-batch membership, it neither owes
nor releases claims (no forge write reaches its repo), the driver plans no action for it, `drive`
asks for no checkout of its repo, and it holds no wave open.
R6. The board draws a `left-scope` batch in the Done column with the pill `repo left this scope`
and offers no Jump command for it; `batch list` marks it `repo left this scope` when facts are
present.
R7. `fr triage batch focus` on a `left-scope` batch refuses with a message that says its repo
left the scope and names `fr triage batch cancel <id> --orphaned`.
R8. `fr triage batch cancel <id> --orphaned` retires a `left-scope` batch: it appends only the
cancel event (no label, comment or claim write, and no checkout), and its plan says the repo
left the scope so nothing on the forge is withdrawn. `cancel` without `--orphaned` on a
`left-scope` batch refuses and names the flag; `--orphaned` on any other batch refuses.
R9. `docs/explainers/fr-triage.md` names the `left-scope` stage and `batch cancel --orphaned`.

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
        message += f"; taking back its start record failed too: {fail_text(back)}"
    return self._dispatch_failed(members[0], message, exc), False
```

- `_collected_close_out`: as above. `save_closeouts` raises `TriageError` without printing
  (`fr/triage/batch.py:610`).
- `_close_out`: its take-back calls `_save` (the non-printing writer `_write` wraps,
  `triage_batch_cmd.py:854-873`) inside the guard, so no `error:` line is printed by `_fail`
  (`triage_cmd.py:113`); `TriageError` and `VisibilityUnreadable` are caught by the same
  `except Exception`.
- `fail_text(exc)` lives in `fr/triage/drive_errors.py` beside `FAIL_MESSAGE` (`:37`): the message
  a `fail_exit` carries, else `str(exc)`; the boundary's own read (`drive_errors.py:131`) uses it.
- The dedupe key `_dispatch_failed` (`:7676`) builds stays the dispatch error's, so a take-back
  that keeps failing is said once.

### #1626 — `left-scope` (R4-R9)

One predicate, `left_scope(batch, facts)` in `fr/triage/batch.py`: `batch_repo(batch, facts) is
None` and no `facts.warnings` entry has `source == "repos"` (the org list cut at its limit,
`fr/triage/collect.py:273-280`). Every reader below asks it, or reads the stage it derives.

- `fr/triage/batch.py`: `BatchStage` and `BATCH_STAGES` gain `left-scope`; `CLOSED_OUT` holds it.
  `derive_batch_stage` checks, in order: last lifecycle event a cancel → `cancelled`;
  `left_scope` → `left-scope`; then today's table (no events → obsolete/proposed, PR-derived).
- `fr/triage/claims.py`: `owed_claims` skips a `left-scope` batch; `releasing` does not hold it,
  so no release is planned either (`claim_sync.plan_sync`, `claim_sync.py:120-140`, plans nothing
  for it).
- `fr/triage/wave_queue.py` `TERMINAL_STAGES` (`:94`) holds it, so `wave_landings_done`
  (`batch_drive.py:1665`) and `finished_waves` count it finished. `batch_drive.drive_pass`'s held
  filter (`:1781`) and `views.preselected_wave`'s live filter (`views.py:754`) leave it out;
  `views.cancelled_waves` (`:729`) counts it delivered (it may have merged before the move).
- `fr/triage/kanban.py`: `_COLUMN_OF_STAGE["left-scope"] = "done"`; `column_of` (`:438`) and
  `lanes.lane_of` (`lanes.py:36`) read the stage before their `not batch.events` branch, so a
  never-dispatched `left-scope` batch is in Done too; `_TERMINAL_STAGES` (`:311`) holds it;
  `pill_of` (`:459`) maps a stage to its pill text through a mapping that defaults to the stage
  name, `left-scope` → `repo left this scope`, which `fallback_hint` (`:594`) reuses; `show_jump`
  (`:773`) is false for it.
- `fr/triage/render.py` (`:195-199`) and `fr/triage/history.py` (`:52-56`): a
  `.pill.bstage-left-scope` rule beside the other stage pills.
- `commands/triage_batch_cmd.py`:
  - `build_driver` (`:8140`): `names` leaves out every chosen batch that `left_scope` holds,
    reading the scope's `facts.json` when it exists (absent → today's behaviour), so `drive`
    asks for no checkout of a departed repo.
  - `batch_list_command` (`:898`): with facts, a `left-scope` batch's row ends `repo left this
    scope`.
  - `batch_cancel_command` (`:1086`): a `--orphaned` flag. Its checks come before the
    `CLOSED_OUT` refusal (`:1102`) and the `batch_repo` refusal (`:1104`): a `left-scope` batch
    without it refuses naming the flag; with it on any other stage it refuses; with it on a
    `left-scope` batch the plan prints `repo <name> left this scope: nothing on the forge is
    withdrawn` and the cancel-event line, and `--yes` appends the cancel event through `_write`.
- `commands/triage_kanban_cmd.py` `batch_focus_command` (`:185`): the R7 refusal before the
  `batch_repo` check (`:201-203`).
- `docs/explainers/fr-triage.md`: the stage list names `left-scope`, what it means, and
  `batch cancel --orphaned` (R9).

## Design shape

```text
packages/fr/src/fr/
├── commands/
│   ├── triage_batch_cmd.py
│   │   ├── _Driver._collected_close_out   ~ take-back guarded; one line, both errors (R1-R3)
│   │   ├── _Driver._close_out             ~ same, through the non-printing _save
│   │   ├── build_driver                   ~ no checkout asked for a left-scope batch (R5)
│   │   ├── batch_list_command             ~ "repo left this scope" marker (R6)
│   │   └── batch_cancel_command           ~ --orphaned retires a left-scope batch (R8)
│   └── triage_kanban_cmd.py
│       └── batch_focus_command            ~ refusal naming cancel --orphaned (R7)
└── triage/
    ├── drive_errors.py                    + fail_text(exc)
    ├── batch.py                           + left_scope(); "left-scope" in BatchStage, CLOSED_OUT
    ├── claims.py                          ~ owed_claims skips left-scope (R5)
    ├── wave_queue.py                      ~ TERMINAL_STAGES += left-scope (R5)
    ├── batch_drive.py, views.py           ~ held / live filters leave it out (R5)
    ├── kanban.py, lanes.py                ~ Done column, pill text, terminal, no Jump (R6)
    └── render.py, history.py              + .pill.bstage-left-scope
docs/explainers/fr-triage.md               ~ left-scope + cancel --orphaned (R9)

left_scope(batch, facts) = batch_repo(batch, facts) is None
                           and no facts.warnings[source == "repos"]

derive_batch_stage(batch, facts):
    last lifecycle event is cancel  -> cancelled
    left_scope(batch, facts)        -> left-scope            (new)
    no lifecycle events             -> obsolete | proposed
    no PR / open / closed           -> dispatched | pr-open | abandoned
    merged                          -> merged | partial
```

## Verification

strategy: none
settle.conflicts: report — batch closeout-state: the wave driver owns this PR's mergeability
settle.ci: report — batch closeout-state: the wave driver owns this PR's CI

- closeout-takeback-both-errors: none — unit tests drive both close-out starts with a runner whose dispatch raises and a store whose write raises, in CI
- batch-left-scope-stage: none — unit tests over `derive_batch_stage` (repo missing, list truncated, never dispatched), claims, the pure pass, `build_driver` and the board render with a facts file lacking the repo, in CI
- batch-left-scope-cancel: none — unit tests of `batch focus` and `batch cancel --orphaned` against a state directory whose facts lack the repo, in CI

## Out of scope

- Collect appending a stored `repo_left_scope` event (judgements schema 15): the stage is derived.
- Stopping the driver on a failed take-back.
- `fr triage check` listing left-scope batches.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-27-closeout-state | `derio-net/super-fr` | `2026-11-27-closeout-state` | — |
