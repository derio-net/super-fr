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

<!-- fr:journal kind=finding scope=spec id=s1-r1 created=2026-11-27T14:50:03+00:00 state=open review_scope=in -->
### s1-r1 · finding [open] (reviewer: in scope) · A path deleted in the repo can never be fixed by the remedy: R5 refuses an --only path the repo-side root does not have

R2's `deleted` kind names a path absent from `<dir>/<scope>/`, so the `--only <path>` R3/R4 print for it is refused by R5 (state_sync.py:131, `durable_entries` lists only existing files); the driver never forces, so the Need stands for good. State the remedy per kind, and how to keep the state's version from a driver stop.

<!-- fr:journal kind=finding scope=spec id=s1-r2 created=2026-11-27T14:50:03+00:00 state=open review_scope=in -->
### s1-r2 · finding [open] (reviewer: in scope) · The motivating case is fixed only halfway: a repo-only durable file (decomposition.html) is never reported

R2 requires the state to have the path, and `find_drift` walks only the state (state_sync.py:245-271, `_sync` never deletes), so importing `architecture/manifest.yaml` alone leaves the state's manifest naming a fragment it does not hold. Report repo-only files the record does not name too.

<!-- fr:journal kind=finding scope=spec id=s1-r3 created=2026-11-27T14:50:03+00:00 state=open review_scope=in -->
### s1-r3 · finding [open] (reviewer: in scope) · The new Need kind `export-drift` has no NEED_LABELS entry: the Batches page render raises KeyError

views.py:255 `NEED_LABELS`, render.py:1000 `NEED_LABELS[r.kind]` (plain subscript), views.py:235-249 the kind list. Add the label, the comment entry and a test.

<!-- fr:journal kind=finding scope=spec id=s1-r4 created=2026-11-27T14:50:03+00:00 state=open review_scope=in -->
### s1-r4 · finding [open] (reviewer: in scope) · The Need reads its paths back out of a free-text stop reason, and its import command can point at the wrong directory and state

merge_stops.py:29-35 (`MergeStop` is head/reason/at), triage_state_cmd.py:196-219 (`--from` relative to cwd). Parsing paths out of `reason` breaks on odd names; `--from docs/triage` must be run in a default-branch checkout at or after the stop's head; the `else docs/triage` fallback cannot occur while exporting and would print a wrong path; a `--dir` driver targets a state a plain `--repo` import does not reach.

<!-- fr:journal kind=finding scope=spec id=s1-r5 created=2026-11-27T14:50:03+00:00 state=open review_scope=in -->
### s1-r5 · finding [open] (reviewer: in scope) · Symlink handling on the repo side of the drift check and the record read is unspecified (security lens)

state_sync.py:150-157, 171-183, 209-242, 253-255. Say `read_record` and `find_drift` read through O_NOFOLLOW descriptors, what a repo-side symlink at a durable path is for drift, and what an `--only` path matching a symlink does; test each.

<!-- fr:journal kind=finding scope=spec id=s1-r6 created=2026-11-27T14:50:03+00:00 state=open review_scope=in -->
### s1-r6 · finding [open] (reviewer: in scope) · An unreadable or unparseable record has no remedy, and the driver shows only a generic refusal

triage_batch_cmd.py:7896-7898 (a plain TriageError is a refusal with no stop and no Need). Say whether `--force` rewrites a bad record, and give the driver its own stop and Need for it.

<!-- fr:journal kind=finding scope=spec id=s1-r7 created=2026-11-27T14:50:03+00:00 state=open review_scope=in -->
### s1-r7 · finding [open] (reviewer: in scope) · The record's line format cannot represent every path a durable file may have

state_sync.py:112-128 (`_walk` yields any file name). A newline or backslash in a name breaks `<sha256>  <path>` lines; define an escape or refuse, and pin the round trip.

<!-- fr:journal kind=finding scope=spec id=s1-r8 created=2026-11-27T14:50:03+00:00 state=open review_scope=in -->
### s1-r8 · finding [open] (reviewer: in scope) · The Verification rows do not cover several requirements: --force, the --only refusals, the stop clearing, and the record kept out of import

Widen the three rows' reasons or add rows so every requirement is covered; state that a hand `fr triage state export` never touches the driver's stops.

<!-- fr:journal kind=finding scope=spec id=s1-r9 created=2026-11-27T14:50:03+00:00 state=open review_scope=out -->
### s1-r9 · finding [open] (reviewer: out of scope) · A targeted import writes the state directory under a running driver with no drive.lock check

triage_state_cmd.py:196-223 (import takes no lock), triage_batch_cmd.py:7893. Import was lock-free before this change; worth a follow-up, not a blocker.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-27T14:50:03+00:00 -->
### spec-review-1 · review · independent spec review: 9 findings (8 in scope, 1 out)

Findings s1-r1 … s1-r8 (in scope) and s1-r9 (out of scope). The five operator decisions (d-record-location, d-bootstrap, d-hand-export, d-only-semantics, d-verification) are honoured. Named code verified at file:line by the reviewer (state_sync.py, merge_stops.py, views.py, render.py, model.py, triage_state_cmd.py, triage_batch_cmd.py, the fr-triage skill and the three docs pages).

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-27T14:50:03+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · new refusal paths (drift, a bad record, --only refusals, the driver stop) each need an operator-facing remedy that actually works

<!-- fr:journal kind=finding scope=spec id=s1-r1-resolved created=2026-11-27T14:50:03+00:00 state=fixed resolves=s1-r1 -->
### s1-r1-resolved · finding [fixed] · resolves s1-r1: A path deleted in the repo can never be fixed by the remedy: R5 refuses an --only path the repo-side root does not have

R5 now removes from the state a named path the repo lacks (reported `removed`), so `deleted` drift is taken in; R3/R4 name `export --force` to keep the state's version.

<!-- fr:journal kind=finding scope=spec id=s1-r2-resolved created=2026-11-27T14:50:03+00:00 state=fixed resolves=s1-r2 -->
### s1-r2-resolved · finding [fixed] · resolves s1-r2: The motivating case is fixed only halfway: a repo-only durable file (decomposition.html) is never reported

R2's `added` kind now covers a repo file the record does not name whether or not the state has it; find_drift walks the union of state, repo and record.

<!-- fr:journal kind=finding scope=spec id=s1-r3-resolved created=2026-11-27T14:50:03+00:00 state=fixed resolves=s1-r3 -->
### s1-r3-resolved · finding [fixed] · resolves s1-r3: The new Need kind `export-drift` has no NEED_LABELS entry: the Batches page render raises KeyError

R4 and the Design add NEED_LABELS['export-drift'], the Need kind comment and a render test.

<!-- fr:journal kind=finding scope=spec id=s1-r4-resolved created=2026-11-27T14:50:03+00:00 state=fixed resolves=s1-r4 -->
### s1-r4-resolved · finding [fixed] · resolves s1-r4: The Need reads its paths back out of a free-text stop reason, and its import command can point at the wrong directory and state

The stop's reason is now the whole operator text, built in _export from the config it holds (shell-quoted args, the sha to be at or after, --dir when overridden); the Need shows it, parsing nothing.

<!-- fr:journal kind=finding scope=spec id=s1-r5-resolved created=2026-11-27T14:50:03+00:00 state=fixed resolves=s1-r5 -->
### s1-r5-resolved · finding [fixed] · resolves s1-r5: Symlink handling on the repo side of the drift check and the record read is unspecified (security lens)

R2/R5 and the Design: the record and repo files are read through O_NOFOLLOW descriptors; a repo-side symlink is never drift, skipped as SYMLINK_DEST; a named symlink is skipped, never followed or removed.

<!-- fr:journal kind=finding scope=spec id=s1-r6-resolved created=2026-11-27T14:50:03+00:00 state=fixed resolves=s1-r6 -->
### s1-r6-resolved · finding [fixed] · resolves s1-r6: An unreadable or unparseable record has no remedy, and the driver shows only a generic refusal

R3: a bad record is refused naming the file and --force rewrites it; R4: the driver records the same export-drift stop and Need for it (BadRecord).

<!-- fr:journal kind=finding scope=spec id=s1-r7-resolved created=2026-11-27T14:50:03+00:00 state=fixed resolves=s1-r7 -->
### s1-r7-resolved · finding [fixed] · resolves s1-r7: The record's line format cannot represent every path a durable file may have

R1: the record is JSON, which escapes any file-name character; the Verification row names the round trip.

<!-- fr:journal kind=finding scope=spec id=s1-r8-resolved created=2026-11-27T14:50:03+00:00 state=fixed resolves=s1-r8 -->
### s1-r8-resolved · finding [fixed] · resolves s1-r8: The Verification rows do not cover several requirements: --force, the --only refusals, the stop clearing, and the record kept out of import

The three Verification reasons now name every behaviour of R1-R5; R4 states a hand export never reads or writes the driver's stops.

<!-- fr:journal kind=finding scope=spec id=s1-r9-resolved created=2026-11-27T14:50:03+00:00 state=open resolves=s1-r9 out_of_scope=true -->
### s1-r9-resolved · finding [out-of-scope] · resolves s1-r9: A targeted import writes the state directory under a running driver with no drive.lock check

fr triage state import has never taken drive.lock; this change adds a selector, not the lock-free write. It is a separate hazard of the existing command.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-27T14:50:06+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  export-drift-driver-need: none
  export-drift-refused: none
  targeted-import-only: none
row_kinds:
  export-drift-driver-need: none
  export-drift-refused: none
  targeted-import-only: none
run_gate: developer
run_kind: none
```

<!-- fr:journal kind=finding scope=spec id=s1-r9-resolved-2 created=2026-11-27T16:48:04+00:00 state=open resolves=s1-r9 tracked_by=https://github.com/derio-net/super-fr/issues/1742 -->
### s1-r9-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1742] · resolves s1-r9: A targeted import writes the state directory under a running driver with no drive.lock check

Filed at deliver as https://github.com/derio-net/super-fr/issues/1742.
