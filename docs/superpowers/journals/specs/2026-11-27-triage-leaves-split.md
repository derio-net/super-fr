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

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-27T19:59:06+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · R11 names two of the four pages fr docs check will report; fr-triage.md and herdr-control-sessions.md are missing

fr-triage.md covers fr/triage/** and herdr-control-sessions.md covers triage/batch*.py; both go stale with this change.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-27T19:59:06+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · handback_rules.py also needs Iterable from collections.abc

closeout_handback_decision is annotated with Iterable; handback_rules imports only Callable and Sequence.

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-27T19:59:06+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · R9 contradicts R8 and R10, which change three tests

R9 said no test assertion changes; R8 rewrites the purity tests and R10 the budget constant.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-27T19:59:06+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · Three line citations in Background are off or mis-ordered

test def at :717 not :719; re-export block 44-55 not 45-56; type names paired with lines in reverse order.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-11-27T19:59:06+00:00 -->
### spec-review · review · independent spec review: 4 findings

fr-spec-reviewer checked decisions q1-q5 (all honoured), the no-cycle claim (holds: export bodies use only Action, Admitted, LivePr, CONFLICTING, _wrong_base, EXPORT_PREFIX, Batch, Export, Snapshot as annotation; hand-back bodies only model events and handbacks_since), and every cited file:line. Findings s-r1..s-r4, all in scope.

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-27T19:59:06+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: R11 names two of the four pages fr docs check will report; fr-triage.md and herdr-control-sessions.md are missing

R11 and the Design shape now name fr-triage.md and herdr-control-sessions.md with the same stamp; their globs already match the new modules.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-27T19:59:06+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: handback_rules.py also needs Iterable from collections.abc

Design now says handback_rules adds Iterable to its collections.abc import and grows by what the moved bodies use.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-27T19:59:06+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: R9 contradicts R8 and R10, which change three tests

R9 reworded: no test assertion changes other than R8's and R10's.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-27T19:59:06+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: Three line citations in Background are off or mis-ordered

Citations corrected to :717 and :44-55; type names listed in line order.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-27T19:59:08+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates: {}
row_kinds: {}
run_gate: developer
run_kind: none
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-triage-leaves-split-p1 created=2026-11-27T20:01:26+00:00 -->
### phase-split-2026-11-27-triage-leaves-split-p1 · decision · tier: the plan's one standard-tier phase; the spec carries no acceptance rows (operator decision q5-rows: a no-behaviour refactor), so no row can name its ask

R1-R12 are all served by this single phase.
