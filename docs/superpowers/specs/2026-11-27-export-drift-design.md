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
beside `exported-by`: JSON, `{"schema": 1, "files": {<path>: <sha256>}}`, one entry per durable
regular file the export left equal to the state's copy (copied or already identical), the path
POSIX and relative to the root (JSON escapes any character a file name holds). It is not
durable state: import never reads or copies it.

R2. Before it writes anything, an export that finds a record compares the repo-side root with it
and with the state. A durable path is drift when the repo's copy differs from the state's and one
of these holds: `changed` (the record names it with another sha256 than the repo's copy), `deleted`
(the record names it, the repo no longer has it, and the state has it), or `added` (the record
does not name it and the repo has it, whether or not the state has it). With no record, nothing is
drift. A repo-side durable path that is a symlink, or lies under one, is never drift: the export
skips it as today (`SYMLINK_DEST`) and reports it. Every repo-side file and the record are read
through `O_NOFOLLOW` descriptors from the root, as the copy writes them.

R3. An export with drift writes nothing (no file, no stamp, no record) and fails with an error that
names every drifted path with its kind and the remedy: to keep the repo's edit, import those paths
with `fr triage state import --from <dir> --only <path> …` (run in a checkout of the default
branch), then export again; to keep the state's version, `fr triage state export --force`, which
overwrites the drifted paths and rewrites the record. A record that is a symlink or does not parse
is refused the same way, naming the file, and `--force` rewrites it too. Its exit code is 2, as for
any refusal.

R4. The driver's per-wave export never forces. On drift, or on a record it cannot read, it commits
and pushes nothing, opens no PR, and records a merge stop keyed `export-drift:<repo>` whose reason
is the whole operator text: the paths with their kinds, the exact import command (each argument
shell-quoted: `--repo <repo>`, `--from <export path>`, one `--only` per `changed` or `added` path,
or the record's file named for a bad record), the default-branch sha the checkout must be at or
after, and the `--force` alternative. While the stop stands, "Needs you now" shows one
`export-drift` row (label "Triage export drifted from the repo") whose text is that reason. The
export stays owed. The driver's next export of that repo that finds no drift and a readable record
clears the stop; a hand `fr triage state export` never reads or writes the driver's stops.

R5. `fr triage state import` takes `--only <path>`, repeatable. Each path is a file or a directory
relative to `<dir>/<scope>/`; a directory names every durable file below it. Only the named files
change in the state: each one the repo has is copied, even when the state's copy has a newer mtime,
and each one the state has but the repo does not is removed from the state (reported `removed`), so
a `deleted` drift is taken in too. No other state file is read or changed. A named symlink, on
either side, is skipped and reported as today, never followed or removed. A path that is not a
plain relative path, or names no durable file of either the repo-side root or the state, is refused
(exit 2) before anything is copied or removed.

R6. `docs/triage/README.md` and the `fr-triage` skill say which way the state flows: the state
directory is the source, the repo copy is written only by an export, and a direct edit under
`docs/triage/<scope>/` must also reach the state (by a targeted import) before the next export.
The pages that cover the export and import (`docs/explainers/fr-triage.md`,
`docs/explainers/fr-wave-driver.md`) describe R1–R5.

## Design

**Record and drift (`state_sync.py`).** A constant `RECORD_FILE = "exported-files"`.
`read_record(root)` opens it from the root's descriptor with `O_NOFOLLOW` (`_open_dir`, `_open`)
and returns `None` when absent; a symlink, a non-regular file, bad JSON or a wrong schema is a
`BadRecord(TriageError)` naming it. `_hash(root, rel)` hashes a repo-side file through the same
descriptor path (`None` when absent, or a symlink skip). `find_drift(state_dir, root, record)`
walks the union of `durable_entries(state_dir)`, `durable_entries(root)` and the record's paths
(regular files only; a symlink entry on either side, or a repo path `_symlinked_dest` reports, is
left out) and returns a tuple of `Drift(path, kind)` by R2. `class ExportDrift(TriageError)` carries
the drift tuple; its message is R3's.

`export_state(..., force=False)`: after `_stamp`, read the record; unless `force`, a `BadRecord`
propagates and drift raises `ExportDrift`, both before `_sync`. After `_sync`, write the record
from the report (every path in `copied` plus every path skipped as `IDENTICAL`, hashed from the
root), from the root's descriptor like the stamp, and add it to `copied` only when its bytes
changed, so an export with nothing new still leaves the driver's `head is None` path untouched.

**Hand command.** `fr triage state export` gains `--force` ("overwrite files changed in the repo
since the last export, and a bad record"). Both errors reach `_refuse` like any `TriageError`.

**Driver (`triage_batch_cmd.py`, `_export`).** Catch `ExportDrift` and `BadRecord` before the
generic `TriageError`: count a refusal (`_export_refusals += 1`), build the R4 text (`shlex.quote`
on every argument; `--from` is `config.path`, read here where `_export` already holds the config;
`--dir <state dir>` added when the driver was started with a `--dir` override), record
`MergeStop(head=<origin/default sha>, reason=<text>, at=now)` under
`export_drift_stop_key(repo)` (`merge_stops.py`, `export-drift:<repo>`), and return "refused,
nothing committed or pushed: …". An export that passes the drift check clears that stop.

**Need (`views.py`).** `export_drift_needs(stops)` returns one `Need("export-drift", repo,
stop.reason, None)` per `export-drift:` stop; `needs_you` adds them next to
`archive_conflict_needs`. `NEED_LABELS` gains `"export-drift": "Triage export drifted from the
repo"` and the kind comment on `Need` names it; a render test covers the row.

**Targeted import.** `import_state(..., only=None)`: with `only`, each path is checked as a plain
relative path (`contained`'s rule) and expanded against `durable_entries(root)` and
`durable_entries(state_dir)` (equal to the path, or below it as a directory); an unmatched path is
a `TriageError` before any write. `_sync` takes an optional selected set and runs with
`keep_newer=False` for it; a selected state file the repo lacks is unlinked from its parent's
descriptor (`os.unlink(name, dir_fd=…)`, never through a symlinked parent) and reported in a new
`SyncReport.removed`. The command adds `--only` (repeatable) and prints `removed <path>` lines.

**Docs.** README: a "Which way it flows" paragraph, the `exported-files` row, and the targeted
import in the regeneration recipe; skill line 15 and the two explainers updated, with their
`reviewed` stamps. Mirrors regenerated (`sync-opencode.py`, `sync-hermes.py`); a `minor` change
fragment (new flags).

## Design shape

```
packages/fr/src/fr/triage/
  state_sync.py   + RECORD_FILE "exported-files" (JSON), read_record, _hash, find_drift
                  + Drift, ExportDrift, BadRecord;  SyncReport + removed
                  ~ export_state(force=)  record + drift check before _sync; writes the record after
                  ~ import_state(only=)   named paths only: copied, or removed when the repo lacks them
  merge_stops.py  + export_drift_stop_key(repo) -> "export-drift:<repo>"
  views.py        + export_drift_needs(stops); NEED_LABELS["export-drift"]; needs_you adds its rows
packages/fr/src/fr/commands/
  triage_state_cmd.py  ~ export --force; import --only (repeatable), prints removed
  triage_batch_cmd.py  ~ _export: ExportDrift|BadRecord -> stop (full text) + refusal; clean -> clear

export flow:
  stamp ok? ─▶ record? ─no─▶ copy ─▶ write record
                  │yes (bad: refuse unless --force)
                  ▼
           find_drift ─none─▶ copy ─▶ write record
                  │some
                  ▼
     hand: exit 2 (or --force: copy)    driver: stop + Need, push nothing
```

## Verification

strategy: none
- export-drift-refused: none — unit tests in this PR's CI write and read back the record, export over a changed, a deleted and an added file and a bad record and assert the refusal, its message and that nothing was written, the no-record bootstrap, symlinks skipped, and --force overwriting and rewriting the record
- export-drift-driver-need: none — unit tests in this PR's CI run the driver's export over drift and a bad record and assert no push, the stop's text, the Need row and its label on the rendered page, and the stop cleared by a clean export
- targeted-import-only: none — unit tests in this PR's CI import with --only and assert only the named paths moved (a newer state copy overwritten, a path the repo lacks removed, symlinks skipped) and that a bad or unmatched path is refused before any write
gate: developer
settle.conflicts: report — batch export-drift: the wave driver owns this PR's mergeability
settle.ci: report — batch export-drift: the wave driver owns this PR's CI

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-27-export-drift | `derio-net/super-fr` | `2026-11-27-export-drift` | — |
