```text
packages/fr/src/fr/
├── commands/
│   ├── triage_batch_cmd.py
│   │   ├── _Driver._collected_close_out   ~ take-back guarded; dispatch + take-back errors, one line
│   │   ├── _Driver._close_out             ~ same, through the non-printing _save
│   │   ├── _Driver._dispatch_failed       ~ `also` text said with the line, kept out of the dedupe key
│   │   ├── build_driver                   ~ facts via _previous_facts; no checkout for a left-scope batch
│   │   ├── batch_list_command             ~ "repo left this scope" marker (with facts)
│   │   └── batch_cancel_command           ~ --orphaned -> fr.triage.orphan
│   └── triage_kanban_cmd.py
│       └── batch_focus_command            ~ refuses a left-scope batch, names cancel --orphaned
└── triage/
    ├── drive_errors.py                    + fail_text(), takeback_failed()
    ├── batch.py                           + left_scope(); "left-scope" in BatchStage, CLOSED_OUT
    ├── orphan.py                          + the cancel --orphaned checks and plan lines
    ├── checkouts.py                       + checkout_map (moved from triage_batch_cmd)
    ├── claims.py, claim_sync.py           ~ no claim, refresh or release op for a left-scope batch
    ├── wave_queue.py, batch_drive.py      ~ terminal for waves; held filter leaves it out
    ├── views.py                           ~ preselected_wave skips it
    ├── kanban.py, kanban_render.py        ~ Done column, pill "repo left this scope", no Jump
    └── render.py, history.py              + .pill.bstage-left-scope
docs/explainers/fr-triage.md               ~ left-scope stage, cancel --orphaned

derive_batch_stage(batch, facts):
    last lifecycle event is cancel  -> cancelled
    left_scope(batch, facts)        -> left-scope   (repo not in facts.repos, list not truncated)
    no lifecycle events             -> obsolete | proposed
    PR table                        -> dispatched | pr-open | abandoned | merged | partial
```
