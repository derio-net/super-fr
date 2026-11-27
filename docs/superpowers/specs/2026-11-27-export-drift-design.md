# Triage export refuses to overwrite a repo-side edit; targeted import

## Background

`fr.triage.state_sync.export_state` (`packages/fr/src/fr/triage/state_sync.py`) copies every
durable file and directory (`DURABLE_FILES`, `DURABLE_DIRS`) from a scope's state directory
over the repo-side root `<dir>/<scope>/`. It keeps no record of what it wrote last, so it
cannot tell a file the state changed from a file someone edited in the repo. A direct edit
under `docs/triage/<scope>/` is reverted by the next export, with nothing reported.

Issue #1667 records this live: #1525 added `architecture/decomposition.html` to
`docs/triage/derio-net--super-fr/` and listed it in that directory's `manifest.yaml`, without
touching the live state. The wave 22 export (PR #1664) wrote the older `manifest.yaml` back.
One test happened to pin that fragment, so CI went red and the driver stopped; any other
direct edit would have been reverted silently. Recovery was by hand.

Two writers use `export_state`: the hand command `fr triage state export --to <dir>`
(`packages/fr/src/fr/commands/triage_state_cmd.py`, `export_command`) and the driver's
per-wave export, `_Driver._export` (`packages/fr/src/fr/commands/triage_batch_cmd.py`), which
exports into a fresh worktree of `origin/<default>`, commits only `<path>/<scope>/`, pushes and
opens a PR. A `TriageError` from `export_state` there is a refusal: nothing is committed or
pushed, `_export_refusals` counts it, and the pass reports it as blocked.

`import_state` copies the whole repo-side root back into the state directory, skipping a state
file whose mtime is newer unless `--force`. There is no way to take in one file only, so
importing one fragment can roll back newer judgements.

The driver's "Needs you now" rows (`fr.triage.views.needs_you`) read its recorded merge stops
(`fr.triage.merge_stops`, `merge-stops.json`); `archive_conflict_needs` turns an `export:<repo>`
conflict stop into a row.

Operator decisions (brainstorm round 1): the record is a committed manifest in the repo-side
root; with no record yet, the export proceeds and writes the first one; both the hand command and
the driver refuse drift, and only the hand command can force past it; `--only` paths are always
imported; verification is CI unit tests, with no gate.

## Requirements

R1. Every export writes a record file `exported-files` in the repo-side root `<dir>/<scope>/`,
beside `exported-by`. It holds one line per durable file the export left equal to the state's
copy (copied or already identical): the file's sha256 and its path relative to the root. It is
not durable state: import never reads or copies it.

R2. Before it writes anything, an export that finds a record compares the repo-side root with it.
A path is drift when the state has it, the repo's copy differs from the state's, and either the
record names it with a different sha256 (changed in the repo), the record names it and the repo
no longer has it (deleted in the repo), or the record does not name it and the repo has it
(added in the repo). With no record, nothing is drift.

R3. An export with drift writes nothing (no file, no stamp, no record) and fails with an error
that names every drifted path with its kind (changed, deleted, added) and the remedy: import
those paths with `fr triage state import --from <dir> --only <path> …`, then export again.
`fr triage state export --force` overwrites the drifted paths instead; its exit code on drift is
2, as for any refusal.

R4. The driver's per-wave export never forces. On drift it commits and pushes nothing, opens no
PR, and records a merge stop keyed `export-drift:<repo>` whose reason names the paths. While the
stop stands, "Needs you now" shows one `export-drift` row for the repo naming the paths and the
exact import command (with `--repo <repo>`, `--from <export path>` and one `--only` per path). The
export stays owed. An export of that repo that finds no drift clears the stop.

R5. `fr triage state import` takes `--only <path>`, repeatable. Each path is a file or a
directory relative to `<dir>/<scope>/`; a directory names every durable file below it. Only the
named files are copied, even when the state's copy has a newer mtime; no other state file is
read or changed. A path that is not a plain relative path, or names no durable file of the
repo-side root, is refused (exit 2) before anything is copied.

R6. `docs/triage/README.md` and the `fr-triage` skill say which way the state flows: the state
directory is the source, the repo copy is written only by an export, and a direct edit under
`docs/triage/<scope>/` must also reach the state (by a targeted import) before the next export.
The pages that cover the export and import (`docs/explainers/fr-triage.md`,
`docs/explainers/fr-wave-driver.md`) describe R1–R5.

## Design

**Record and drift (`state_sync.py`).** A constant `RECORD_FILE = "exported-files"`. The format is
`<sha256>  <path>\n` per line, sorted by path, like `sha256sum` output. `read_record(root)` parses it
(`None` when absent; a symlinked record, or one that does not parse, is a `TriageError` naming it,
never "no record"). `find_drift(state_dir, root, record)` walks `durable_entries(state_dir)` (regular
files only; symlinks are skipped as today) and returns a tuple of `Drift(path, kind)` by R2.
`class ExportDrift(TriageError)` carries the drift tuple; its message is R3's.

`export_state(..., force=False)`: after `_stamp`, read the record and, unless `force`, raise
`ExportDrift` before `_sync`. After `_sync`, write the record from the report: every path in
`copied` plus every path skipped as `IDENTICAL`, hashed from the root's file through the same
`O_NOFOLLOW` descriptor path as the copy. The record is written like the stamp (from the root's
descriptor, refusing a symlink) and is added to `copied` when its bytes changed, so the driver's
commit and the hand command's output include it.

**Hand command.** `fr triage state export` gains `--force` ("overwrite files changed in the repo
since the last export"). `ExportDrift` reaches `_refuse` like any `TriageError`.

**Driver (`triage_batch_cmd.py`, `_export`).** Catch `ExportDrift` before the generic `TriageError`:
count it as a refusal (`_export_refusals += 1`), record `MergeStop(head=<origin/default sha>,
reason="drift: <paths>", at=now)` under `export_drift_stop_key(repo)` (`merge_stops.py`,
`export-drift:<repo>`), and return "refused, nothing committed or pushed: …". Any export of the repo
that passes the drift check clears that stop, whatever happens after.

**Need (`views.py`).** `export_drift_needs(stops, export_paths)` returns one `Need("export-drift",
repo, text, None)` per `export-drift:` stop, `text` naming the paths and the import command;
`needs_you` adds it next to `archive_conflict_needs`. The export path comes from the facts' per-repo
config (`facts.config_for(repo).export.path`), else `docs/triage`.

**Targeted import.** `import_state(..., only=None)`: with `only`, each path is checked as a plain
relative path (`contained`'s rule) and expanded against `durable_entries(root)` (equal to the path,
or below it as a directory); an unmatched path is a `TriageError` before any copy. `_sync` takes an
optional set of selected paths and runs with `keep_newer=False` for them. The command adds
`--only` (repeatable).

**Docs.** README: a "Which way it flows" paragraph, the `exported-files` row, and the targeted
import in the regeneration recipe; skill line 15 and the two explainers updated, with their
`reviewed` stamps. Mirrors regenerated (`sync-opencode.py`, `sync-hermes.py`); a `minor` change
fragment (new flags).

## Design shape

```
packages/fr/src/fr/triage/
  state_sync.py   + RECORD_FILE "exported-files", read_record, find_drift, Drift, ExportDrift
                  ~ export_state(force=)  drift check before _sync; writes the record after
                  ~ import_state(only=)   named paths only, always copied
  merge_stops.py  + export_drift_stop_key(repo) -> "export-drift:<repo>"
  views.py        + export_drift_needs(stops, export_paths); needs_you adds its rows
packages/fr/src/fr/commands/
  triage_state_cmd.py  ~ export --force; import --only (repeatable)
  triage_batch_cmd.py  ~ _export: ExportDrift -> stop + refusal; clean drift check -> clear stop

export flow:
  stamp ok? ─▶ record? ─no─▶ copy ─▶ write record
                  │yes
                  ▼
           find_drift ─none─▶ copy ─▶ write record
                  │some
                  ▼
     hand: exit 2 (or --force: copy)    driver: stop + Need, push nothing
```

## Verification

strategy: none
- export-drift-refused: none — unit tests in this PR's CI export over a changed, a deleted and an added file and assert the refusal, its message and that nothing was written
- export-drift-driver-need: none — unit tests in this PR's CI run the driver's export over drift and assert no push, the stop and the Need row
- targeted-import-only: none — unit tests in this PR's CI import with --only and assert only the named paths moved
gate: developer
settle.conflicts: report — batch export-drift: the wave driver owns this PR's mergeability
settle.ci: report — batch export-drift: the wave driver owns this PR's CI

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-27-export-drift | `derio-net/super-fr` | `2026-11-27-export-drift` | — |
