<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-export-drift

<!-- fr:journal kind=discovery scope=spec id=brief-1667 created=2026-11-27T14:43:34+00:00 input=true -->
### brief-1667 · discovery · Operator brief: batch export-drift (super-fr#1667)

Batch `export-drift` of derio-net/super-fr, one issue, one PR on feat/batch-export-drift.
Issue #1667, "Triage export silently reverts direct edits to docs/triage/ (wave 22 export
dropped decomposition.html)". Asks: (1) refuse to overwrite a repo-side change: compare each
durable file on the default branch with what the previous export wrote (recorded per file);
on drift push nothing and record a Need naming the paths and the remedy
`fr triage state import --from docs/triage --only <paths>`, then re-run; (2) a targeted
import of named paths only; (3) document the direction in docs/triage/README.md and the
fr-triage skill; (4) tests: an export over a drifted file refuses and names it, a targeted
import takes only the named paths. Refs #1525, #1664, #1666.

<!-- fr:journal kind=decision scope=spec id=d-record-location created=2026-11-27T14:43:34+00:00 decided_by=operator -->
### d-record-location · decision · The export record is a committed manifest in the repo-side root

`exported-files` beside `exported-by`, path to sha256; travels with the repo copy. Operator chose the recommended option.

<!-- fr:journal kind=decision scope=spec id=d-bootstrap created=2026-11-27T14:43:34+00:00 decided_by=operator -->
### d-bootstrap · decision · With no record yet, the export proceeds and writes the first record

Drift is caught from the second export on. Operator chose the recommended option.

<!-- fr:journal kind=decision scope=spec id=d-hand-export created=2026-11-27T14:43:34+00:00 decided_by=operator -->
### d-hand-export · decision · Both the hand export and the driver refuse drift; only the hand command takes --force

The driver never forces and records a Need instead. Operator chose the recommended option.

<!-- fr:journal kind=decision scope=spec id=d-only-semantics created=2026-11-27T14:43:34+00:00 decided_by=operator -->
### d-only-semantics · decision · `--only` paths (files or directories) are always imported, the mtime check skipped

Every other file is untouched; a path naming no durable file is refused before any copy. Operator chose the recommended option.

<!-- fr:journal kind=decision scope=spec id=d-verification created=2026-11-27T14:43:34+00:00 decided_by=operator -->
### d-verification · decision · Verified by CI unit tests, no walk, gate developer

No post-merge Test Plan row. Operator chose the recommended option.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-27T14:43:34+00:00 lens=security step=brainstorm -->
### lens-security-1 · lens · the export and import write through O_NOFOLLOW descriptors; the new record file and --only paths must keep that symlink and containment discipline
