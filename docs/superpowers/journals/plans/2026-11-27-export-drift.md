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

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-27T16:41:20+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · A record key with a NUL passes _record_path and raises an uncaught ValueError from os.open; the driver export crashes (phase 1)

state_sync.py `_record_path` / `_hash` (reproduced by the reviewer with `{"history/a\u0000b": "x"}`).

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-27T16:41:20+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · A directory at exported-files makes --force fail with 'Is a directory', though the BadRecord text promises --force rewrites it (phase 1)

state_sync.py `_write_root_file`, `BadRecord` (reproduced by the reviewer).

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-27T16:41:20+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · The hand command's ExportDrift remedy commands omit the scope options, so they cannot be pasted as printed (phase 1)

state_sync.py `ExportDrift`; triage_state_cmd.py `export_command`.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-27T16:41:20+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · --only on a state-only path under a repo-side symlinked dir is skipped silently, not reported as R5 requires (phase 1)

state_sync.py, the removal loop in `_sync`.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-27T16:41:20+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · rev_parse/record_stop failures inside the driver's except handler escape the export's error handling (phase 1)

triage_batch_cmd.py `_Driver._export`, the `except (ExportDrift, BadRecord)` handler.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-27T16:41:20+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · Every export hashes or compares each durable file about 4 times; the digests could be reused (phase 1)

state_sync.py `_record_bytes`, `find_drift`. Linear; efficiency only.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-11-27T16:41:20+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · Missing tests: hostile record keys, a directory record, driver deleted drift, the end-to-end import --only then export recovery (phase 1)

tests/unit/test_triage_state_sync.py, tests/unit/test_triage_batch_drive_cmd.py.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-11-27T16:41:20+00:00 phase=1 state=open review_scope=out -->
### p1-r8 · finding [open] (reviewer: out of scope) · The stop's reason embeds the moving default sha, rewriting merge-stops.json each pass (phase 1)

triage_batch_cmd.py `_export` with merge_stops.py `record_stop`. Cosmetic.

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-27T16:41:20+00:00 phase=1 -->
### review-p1-1 · review · phase 1 independent code review: 8 findings (7 in scope, 1 out) (phase 1)

Independent reviewer (separate context, not the implementer) reviewed spec R1-R6, the plan and the diff from the merge-base. Raised p1-r1 … p1-r8. Received: p1-r1, p1-r2, p1-r3, p1-r4, p1-r5 and p1-r7 verified against the code and fixed with tests; p1-r6 refuted (linear, and the second hash is deliberate); p1-r8 refuted (intended). The executor's own open finding p1-bootstrap-repo-only-files-drift-forever was fixed before the review (the record names every durable file the root holds), and the reviewer confirmed it.

<!-- fr:journal kind=finding scope=plan id=p1-bootstrap-repo-only-files-drift-forever-resolved created=2026-11-27T16:41:20+00:00 phase=1 state=fixed resolves=p1-bootstrap-repo-only-files-drift-forever -->
### p1-bootstrap-repo-only-files-drift-forever-resolved · finding [fixed] · resolves p1-bootstrap-repo-only-files-drift-forever: A repo-only durable file present at the first export becomes permanent "added" drift (phase 1)

`_record_bytes` records every durable regular file the root holds after the export, repo-only ones included, so a first or forced export settles them; spec R1 says so. Test: test_a_repo_only_file_at_the_first_export_is_recorded_not_drift_forever.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-27T16:41:20+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: A record key with a NUL passes _record_path and raises an uncaught ValueError from os.open; the driver export crashes (phase 1)

`_record_path` refuses a key holding a NUL; `_hash` turns a ValueError into a TriageError. Test: test_a_hostile_record_key_is_a_bad_record_never_a_path (NUL, .., absolute, non-durable).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-27T16:41:20+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: A directory at exported-files makes --force fail with 'Is a directory', though the BadRecord text promises --force rewrites it (phase 1)

A non-regular record is a BadRecord with forceable=False, and its text says to remove it by hand; export_state refuses a non-regular stamp or record before any copy (`_refuse_non_regular`), so a forced run writes nothing. Test: test_a_directory_record_is_refused_and_force_names_the_hand_fix.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-27T16:41:20+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: The hand command's ExportDrift remedy commands omit the scope options, so they cannot be pasted as printed (phase 1)

export_command re-renders ExportDrift/BadRecord through drift_stop_text with its own scope_args. Test: test_the_export_verbs_remedy_carries_its_own_scope_options.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-27T16:41:20+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: --only on a state-only path under a repo-side symlinked dir is skipped silently, not reported as R5 requires (phase 1)

The removal loop reports Skipped(rel, SYMLINK) for a selected state-only path under a repo-side symlink. Test: test_only_reports_a_state_only_path_under_a_repo_side_symlinked_dir.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-27T16:41:20+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: rev_parse/record_stop failures inside the driver's except handler escape the export's error handling (phase 1)

The default sha is read with the worktree setup, whose failures are export failures; an OSError writing the stop keeps the refusal and says the Need was not recorded.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-27T16:41:20+00:00 phase=1 state=refuted resolves=p1-r6 -->
### p1-r6-resolved · finding [refuted] · resolves p1-r6: Every export hashes or compares each durable file about 4 times; the digests could be reused (phase 1)

Each read is linear in the durable tree; nothing is asymptotically worse. The second hash after the copy is deliberate: the record must name the bytes on disk, read through the same O_NOFOLLOW descriptors, not digests computed before a copy that a racing path swap could have skipped. Reusing digests would trade that for a constant factor on small text trees.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-11-27T16:41:20+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: Missing tests: hostile record keys, a directory record, driver deleted drift, the end-to-end import --only then export recovery (phase 1)

Added the hostile-key, record-named-symlink, directory-record, symlinked-dir --only and end-to-end recovery tests; the driver test now has a `delete` case and mends `edit`/`delete` through `import --only`, the remedy the stop prints.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-11-27T16:41:20+00:00 phase=1 state=refuted resolves=p1-r8 -->
### p1-r8-resolved · finding [refuted] · resolves p1-r8: The stop's reason embeds the moving default sha, rewriting merge-stops.json each pass (phase 1)

Intended: the stop records the default-branch sha the operator's checkout must be at or after, so it must move when main moves; record_stop writes only when head or reason changed, and that is the case.
