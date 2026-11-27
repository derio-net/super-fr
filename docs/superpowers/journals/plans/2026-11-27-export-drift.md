<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-export-drift

<!-- fr:journal kind=decision scope=plan id=p1-drift-only-names-deleted-paths created=2026-11-27T16:29:17+00:00 phase=1 -->
### p1-drift-only-names-deleted-paths · decision · The import command in the drift text carries one --only per drifted path, deleted ones included (phase 1)

R4 says "one `--only` per `changed` or `added` path", while R3 says "import those
paths" and R5 says a targeted import of a path the repo lacks removes it from the
state "so a `deleted` drift is taken in too". Leaving deleted paths out would make a
drift of only deletions print an import with no `--only` at all, which is a full
import (the roll-back the spec exists to avoid). `drift_text` therefore names every
drifted path, for both the hand refusal and the driver's stop.

<!-- fr:journal kind=decision scope=plan id=p1-driver-stop-uses-scope-args created=2026-11-27T16:29:17+00:00 phase=1 -->
### p1-driver-stop-uses-scope-args · decision · The driver's import and --force commands carry its own scope options (phase 1)

The commands in the `export-drift:<repo>` stop use the driver's `scope_args` (the
same `--repo`/`--org` plus `--dir` or `--workspace` every copied driver command
carries, `triage_kanban_cmd.scope_args`), falling back to `--repo <repo>`; R4's
`--repo <repo>` is the single-repo case of it, and `--dir` appears exactly when the
driver was started with one. The text builder and the stop write live in
`state_sync.py` (`drift_text`, `stop_on`) to keep `triage_batch_cmd.py` within its
line budget (8295 of 8300).

<!-- fr:journal kind=finding scope=plan id=p1-bootstrap-repo-only-files-drift-forever created=2026-11-27T16:29:17+00:00 phase=1 state=open review_scope=in -->
### p1-bootstrap-repo-only-files-drift-forever · finding [open] (reviewer: in scope) · A repo-only durable file present at the first export becomes permanent "added" drift (phase 1)

R1 records only files the export left equal to the state's copy, and R2 calls any
repo file the record does not name `added` drift. A repo-side file the state never
had at the bootstrap export is therefore not recorded, and every later export
(hand or driver) refuses on it; `--force` cannot clear it either, since the export
never deletes and the state has no copy to record. This repo has three today:
`docs/triage/derio-net--super-fr/architecture/{closing-order,history-2026-10-02,origins-2026-10-02}.html`
are in the repo copy and not in the live state, so the driver's second export after
this ships would stop with an export-drift Need until someone imports them with
`--only` or deletes them. Implemented as the spec states; the remedy text does say
how to clear it. Options: record repo-only files at the bootstrap (no-record) export,
or have `--force` record what it leaves in place, or import those three files into
the state before this merges.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-27T16:29:17+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

docs, mirrors and the change fragment only: no code to clean
