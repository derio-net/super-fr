<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-triage-leaves-split

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-27T19:55:11+00:00 input=true -->
### brief · discovery · Operator brief: batch arch-triage-leaves (super-fr#1516)

/fr-goal batch arch-triage-leaves — Batch `arch-triage-leaves` of derio-net/super-fr: 1 issue, one PR.
Issue #1516 title: "Split the wave-export and hand-back leaves out of triage/batch_drive.py (the one cheap triage slice)".
Body (summary of the tracker text): decomposition plan for packages/fr/src/fr/triage/batch_drive.py from the #1318
review (section 5.2), P3 refactor, no behaviour change. The slice: wave export (batch_drive.py:1219-1443 at 3d398d19)
and hand-back decisions (:828-1035) to batch_drive_export.py and batch_drive_handback.py, re-exported from
batch_drive; drive_pass, Snapshot and Action stay as one planner. Preserved: drive_pass's action order; every
public name importable from fr.triage.batch_drive. Callers to migrate: none. Guards: widen
test_the_pass_module_reaches_no_runner_git_process_or_clock to a batch_drive*.py glob; lower the budget.
Delivery rules: branch feat/batch-arch-triage-leaves; draft PR with "Closes derio-net/super-fr#1516"; run started
with --issue 1516; no member issue as a phase tracking_issue; no fr pr settle loop (the wave driver owns
mergeability and CI); never add approved-fr.

<!-- fr:journal kind=decision scope=spec id=q1-cycle created=2026-11-27T19:55:11+00:00 decided_by=operator -->
### q1-cycle · decision · Break the export import cycle with a value-types leaf, batch_drive_types.py

Operator chose: move LivePr, Action, Admitted, ChecksVerdict, ActionKind, CONFLICTING (and EXPORT_PREFIX stays with export) into a pure batch_drive_types.py; batch_drive re-exports. Rejected: a lazy import in the leaf; a leaf-local verdict type.

<!-- fr:journal kind=decision scope=spec id=q2-handback-home created=2026-11-27T19:55:11+00:00 decided_by=operator -->
### q2-handback-home · decision · The remaining hand-back decisions move into the existing handback_rules.py

Operator chose one home for every hand-back rule over a new batch_drive_handback.py; the purity guards name handback_rules.py beside the batch_drive*.py glob.

<!-- fr:journal kind=decision scope=spec id=q3-finished-waves created=2026-11-27T19:55:11+00:00 decided_by=operator -->
### q3-finished-waves · decision · finished_waves stays in batch_drive

Operator chose to keep finished_waves (read by board, kanban, history and the triage command) beside closeout_event/is_finished; the export leaf takes export_branch through _stale_orphans.

<!-- fr:journal kind=decision scope=spec id=q4-verification created=2026-11-27T19:55:11+00:00 decided_by=operator -->
### q4-verification · decision · Verification: strategy none, gate developer, the CI suite is the evidence

Operator chose strategy none over a candidate walk: a pure move proves nothing more installed. No Test Plan.

<!-- fr:journal kind=decision scope=spec id=q5-rows created=2026-11-27T19:55:11+00:00 decided_by=operator -->
### q5-rows · decision · No acceptance rows

Operator chose no rows: the change alters nothing a user sees; the import, purity and budget tripwires are the evidence.

<!-- fr:journal kind=discovery scope=spec id=wrong-base-shared created=2026-11-27T19:55:11+00:00 -->
### wrong-base-shared · discovery · _wrong_base is shared by the export row, the collected close-out step and drive_pass

batch_drive.py:1156, :2044, :2053 call it besides _export_row; it moves to batch_drive_types beside LivePr, not to the export leaf.
