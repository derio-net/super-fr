# Split the wave-export and hand-back leaves out of triage/batch_drive.py

Issue: derio-net/super-fr#1516 (architecture review for #1318, section 5.2 of
`docs/superpowers/audits/2026-11-16-architecture-review.md`).

## Background

`packages/fr/src/fr/triage/batch_drive.py` is 2,267 lines against a budget of 2,275
(`tests/unit/test_tripwire_module_budget.py:34`). It is the wave driver's pure pass: it
imports no console, no `typer`, no `fr_dispatch`, runs no git and reads no clock. Two
groups in it are leaves that `drive_pass` (`batch_drive.py:1798`) only calls:

- **wave export** (pages-goal R13, §I step 3b): `export_branch` (`:1283`), `_wave_order`
  (`:1290`), `ExportCount` (`:1294`), `_outside` (`:1297`), `ExportTarget` (`:1308`),
  `export_wave_of` (`:1320`), `export_target` (`:1328`), `_export_row` (`:1369`),
  `_export_actions` (`:1437`) and `_stale_orphans` (`:1478`), with `EXPORT_PREFIX`
  (`:105`);
- **hand-back decisions**: `conflict_at` (`:940`), `fresh_conflicts` (`:949`),
  `conflict_item_id` (`:959`), the archive-conflict section (`ARCHIVE_HANDBACKS_PER_CLOSEOUT`
  `:966` to `archive_conflict_item_id` `:1007`) and the collected close-out hand-back
  (`CLOSEOUT_HANDBACKS` `:1015`, `CloseoutDecisionKind`, `closeout_handback_decision`
  `:1022`).

The issue was written at `3d398d19`. Since then the hand-back budget and the conflict and
red decisions (`handbacks_since`, `conflict_decision`, `red_decision`, `held_conflict`, …)
already left for `fr/triage/handback_rules.py` (spec `2026-11-24-wave-queue-gaps` §E), which
`batch_drive` re-exports by name (`batch_drive.py:44-55`). The rest of the hand-back
decisions use only `fr.triage.model` events and `handbacks_since`.

The export rows build `Action`, `Admitted` and `LivePr` at run time and compare
`LivePr.mergeable` with `CONFLICTING`; all four are defined in `batch_drive.py`
(`CONFLICTING` `:162`, `LivePr` `:171`, `Admitted` `:491`, `Action` `:512`), so an export module that imports them while `batch_drive`
re-exports it would form an import cycle. `_wrong_base` (`:1361`) is used by the export row
and also by the collected close-out step (`:1156`) and by `drive_pass` (`:2044`, `:2053`).
`finished_waves` (`:1263`) is read by the board, kanban, the history page and the triage
command, and stays where it is.

Callers outside the module (`fr/commands/triage_batch_cmd.py`, `fr/triage/views.py`,
`kanban.py`, `wave_queue.py`, and tests) import the moved names from `fr.triage.batch_drive`
and keep doing so through the re-export. `tests/unit/test_triage_batch_drive.py:717`
(`test_the_pass_module_reaches_no_runner_git_process_or_clock`) and
`tests/unit/test_triage_drive_purity.py:39`
(`test_the_drive_pass_reads_no_clock_and_starts_no_process`) check one file each.

## Requirements

R1. The value types the pass and its leaves share — `ChecksVerdict`, `ActionKind`, `LivePr`, `Admitted`, `Action`, `CONFLICTING` and `_wrong_base` — move to a new pure module `fr/triage/batch_drive_types.py`.
R2. The wave-export code — `EXPORT_PREFIX`, `export_branch`, `_wave_order`, `ExportCount`, `_outside`, `ExportTarget`, `export_wave_of`, `export_target`, `_export_row`, `_export_actions` and `_stale_orphans` — moves to a new module `fr/triage/batch_drive_export.py`.
R3. The remaining hand-back decisions — `conflict_at`, `fresh_conflicts`, `conflict_item_id`, `ARCHIVE_HANDBACKS_PER_CLOSEOUT`, `ArchiveConflictKind`, `archive_conflict_decision`, `held_archive_conflict`, `_held_archive_conflict`, `archive_conflict_item_id`, `CLOSEOUT_HANDBACKS`, `CloseoutDecisionKind` and `closeout_handback_decision` — move into the existing `fr/triage/handback_rules.py`.
R4. `finished_waves`, `Snapshot`, `drive_pass` and every other definition stay in `batch_drive.py`.
R5. No import cycle: `batch_drive_types` imports no `fr.triage.batch_drive*` module; `batch_drive_export` imports `batch_drive_types` and never `fr.triage.batch_drive` at run time (`Snapshot` only under `TYPE_CHECKING`); `handback_rules` imports no `fr.triage.batch_drive*` module.
R6. Every name `fr.triage.batch_drive` defines or re-exports today stays importable from it, the moved private names included.
R7. Behaviour is unchanged: `drive_pass` returns the same actions in the same order for every snapshot, and every moved function keeps its name, signature, body and docstring (only import lines change).
R8. The two purity guards cover every module of the pass: `test_the_pass_module_reaches_no_runner_git_process_or_clock` and `test_the_drive_pass_reads_no_clock_and_starts_no_process` check every `fr/triage/batch_drive*.py` file and `fr/triage/handback_rules.py`, and each fails if its file set is empty.
R9. No test assertion changes other than R8's and R10's; tests keep importing from `fr.triage.batch_drive`.
R10. The `batch_drive.py` budget in `test_tripwire_module_budget.py` drops to no more than 50 lines above its new size; `batch_drive.py` stays a held module.
R11. The pages `fr docs check` reports for this change — `docs/explainers/fr-wave-driver.md` and `docs/explainers/index.md` (they cover `batch_drive.py`), `docs/explainers/fr-triage.md` (covers `fr/triage/**`) and `docs/herdr-control-sessions.md` (covers `fr/triage/batch*.py`) — get their `reviewed` stamp moved with the note `still true, module split only`, and `fr-wave-driver.md`'s `covers:` adds the two new modules (the other two pages' globs already match them).
R12. The PR adds the change fragment `.changes/feat-batch-arch-triage-leaves.yaml` with `bump: patch`.

## Design

Every move is a cut and paste. A moved definition keeps its name, docstring and body; only
import lines change.

**`fr/triage/batch_drive_types.py`** holds `ChecksVerdict`, `ActionKind`, `LivePr`,
`Admitted`, `Action`, `CONFLICTING` and `_wrong_base` (a `LivePr` predicate, shared by the
export row, the collected close-out step and `drive_pass`). It imports only the standard
library. Its docstring says it is the pass's value types, split out so the leaves can build
actions without importing the pass.

**`fr/triage/batch_drive_export.py`** holds the export section. It imports `Action`,
`Admitted`, `LivePr`, `CONFLICTING` and `_wrong_base` from `batch_drive_types`, `Batch` and
`Export` from `fr.triage.model`, and `Snapshot` from `fr.triage.batch_drive` under
`TYPE_CHECKING` only (the module has `from __future__ import annotations`).

**`fr/triage/handback_rules.py`** gains the hand-back section, after its own red decision.
It adds `ArchiveConflictEvent`, `CloseoutEvent` and `CloseoutHandbackEvent` to its
`fr.triage.model` import and `Iterable` to its `collections.abc` import (its imports grow by
what the moved bodies use), and its module docstring names the archive-conflict and collected
close-out decisions.

**`fr/triage/batch_drive.py`** imports from all three and re-exports every moved name with
`# noqa: F401 - re-exported` (the existing `handback_rules` import line grows). Its module
docstring says where the leaves went. `ARCHIVE_PREFIXES`, `HOUSEKEEPING_PREFIX` and
`ARCHIVE_WAIT` stay.

**Guards.** Both purity tests iterate over
`sorted(TRIAGE.glob("batch_drive*.py")) + [TRIAGE / "handback_rules.py"]`, asserting the
list holds at least the four files, and run their existing check on each.

**Order of the moves** keeps every intermediate commit importable: the types module first,
then the export leaf, then the hand-back move, then the guards and the budget.

## Design shape

```
packages/fr/src/fr/triage/
  batch_drive.py         ~ keeps Snapshot, Summary, Pass, close-out, finished_waves,
                           drive_pass, lines; re-exports every moved name         R4 R6 R10
  batch_drive_types.py   + ChecksVerdict, ActionKind, LivePr, Admitted, Action,
                           CONFLICTING, _wrong_base (stdlib only)                  R1
  batch_drive_export.py  + EXPORT_PREFIX … _stale_orphans (wave export, §I 3b)     R2
  handback_rules.py      ~ + conflict_at, fresh_conflicts, conflict_item_id,
                           archive-conflict decisions, closeout_handback_decision  R3
tests/unit/test_triage_batch_drive.py   ~ purity guard over batch_drive*.py + handback_rules  R8
tests/unit/test_triage_drive_purity.py  ~ the same file set                                   R8
tests/unit/test_tripwire_module_budget.py ~ batch_drive.py budget lowered                     R10
docs/explainers/{fr-wave-driver,index,fr-triage}.md, docs/herdr-control-sessions.md
                                        ~ reviewed stamp; fr-wave-driver covers the new modules R11
.changes/feat-batch-arch-triage-leaves.yaml + bump: patch                                     R12
```

```
import direction (no cycle, R5):

batch_drive_types   <-  batch_drive_export  <-  batch_drive  (re-export)
batch_drive_types   <-  batch_drive
handback_rules      <-  batch_drive          (re-export)
batch_drive_export  ..> batch_drive.Snapshot (TYPE_CHECKING only)
```

## Verification

strategy: none
gate: developer
settle.conflicts: report — batch arch-triage-leaves: the wave driver owns this PR's mergeability
settle.ci: report — batch arch-triage-leaves: the wave driver owns this PR's CI

The change has no behaviour of its own: the existing suite, unchanged except for the two
widened purity guards and the budget line, is the evidence, run by this PR's CI. No
acceptance rows are added.
