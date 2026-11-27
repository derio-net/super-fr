```
packages/fr/src/fr/triage/
  batch_drive.py         ~ 2267 -> 1879 lines: Snapshot, Summary, Pass, close-out, finished_waves,
                           drive_pass, lines stay; re-exports all 30 moved names (noqa F401)
  batch_drive_types.py   + ChecksVerdict, ActionKind, LivePr, Admitted, Action, CONFLICTING,
                           _wrong_base — stdlib imports only
  batch_drive_export.py  + EXPORT_PREFIX, export_branch … _stale_orphans (wave export, §I 3b);
                           Snapshot under TYPE_CHECKING only
  handback_rules.py      ~ + conflict_at, fresh_conflicts, conflict_item_id, archive-conflict
                           decisions, closeout_handback_decision
  batch_merge, kanban, operator_entries, queue_reports, readiness, views, wave_queue
                         ~ import lines only: moved names from their new homes (mypy
                           no_implicit_reexport)
packages/fr/src/fr/commands/triage_batch_cmd.py, packages/fr/src/fr/settle/managed.py
                         ~ the same import repointing
tests/unit/test_triage_drive_split.py      + import direction (ast, TYPE_CHECKING skipped) and
                                             `is`-identity of every re-exported name
tests/unit/test_triage_batch_drive.py,
tests/unit/test_triage_drive_purity.py     ~ purity guards loop over batch_drive*.py + handback_rules (>= 4)
tests/unit/test_tripwire_module_budget.py  ~ batch_drive.py budget 2275 -> 1900
docs/explainers/{fr-wave-driver,index,fr-triage}.md, docs/herdr-control-sessions.md,
docs/reference/cli.md                      ~ reviewed: still true, module split only
.changes/feat-batch-arch-triage-leaves.yaml + bump: patch
```

```
import direction at run time (no cycle):

batch_drive_types  <-  batch_drive_export  <-  batch_drive (re-export)
batch_drive_types  <-  batch_drive, wave_queue, …
handback_rules     <-  batch_drive (re-export), triage_batch_cmd, …
batch_drive_export ..> batch_drive.Snapshot   (TYPE_CHECKING only)
```
