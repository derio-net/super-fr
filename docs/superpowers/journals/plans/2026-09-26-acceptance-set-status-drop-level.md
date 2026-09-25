# Journal: 2026-09-26-acceptance-set-status-drop-level

<!-- fr:journal kind=decision scope=plan id=p-shape created=2026-09-26T00:44:16 -->
### p-shape · decision · Three phases along the one write path — edit helper (skeleton), engine, CLI+docs+row+bump

drop_levels is the single definition of "on the row" shared by the CLI pre-flight and the engine, so it lands first as the walking skeleton. No manual phase: nothing needs operator action.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-09-26T00:48:32 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · drop_levels typed dict[str, list[str]] forces phase 2 to convert Mapping-of-tuples drops (phase 1)

edit.py:152-154; dict is invariant, so the engine carrier would not type-check without a list() copy.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-09-26T00:48:32 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Removing a ref a row carries twice removes every copy, undocumented and untested (phase 1)

edit.py:171-174 uses a set; the docstring's 'dropped once' was about drops, not existing.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-09-26T00:48:32 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · No test for dropping from a level the row has no refs in (phase 1)

The existing.get(lv, ()) path, e.g. dropping e2e= from a unit-only row.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-09-26T00:48:32 phase=1 state=open review_scope=out -->
### p1-r4 · finding [open] (reviewer: out of scope) · No direct test of merge_levels refusing an unknown key (phase 1)

Pre-existing gap; the shared helper is covered through drop_levels.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-09-26T00:48:32 phase=1 -->
### review-p1 · review · phase 1 code review: 4 minor findings (3 in scope, 1 out) (phase 1)

An independent reviewer reviewed 775cb68b..64f6b5b9 against spec §2 and plan 01.yaml: 18 tests passed, ruff and mypy clean. No critical or important issues. Minor: p1-r1, p1-r2 and p1-r3 are in scope and fixed; p1-r4 is out of scope.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-09-26T00:48:32 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: drop_levels typed dict[str, list[str]] forces phase 2 to convert Mapping-of-tuples drops (phase 1)

drop_levels now takes Mapping[str, Sequence[str]] for both arguments; mypy clean.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-09-26T00:48:32 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Removing a ref a row carries twice removes every copy, undocumented and untested (phase 1)

Docstring states every copy is removed; pinned by test_drop_levels_removes_every_copy_of_a_duplicated_existing_ref.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-09-26T00:48:32 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: No test for dropping from a level the row has no refs in (phase 1)

Added test_drop_levels_refuses_a_drop_from_a_level_the_row_has_no_refs_in.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-09-26T00:48:32 phase=1 state=open resolves=p1-r4 out_of_scope=true -->
### p1-r4-resolved · finding [out-of-scope] · resolves p1-r4: No direct test of merge_levels refusing an unknown key (phase 1)

merge_levels had no direct unknown-key test before this change; the refactor kept its error text byte-identical and drop_levels' test exercises the shared helper.

<!-- fr:journal kind=decision scope=plan id=p2-check-drops-upfront created=2026-09-26T00:52:20 phase=2 -->
### p2-check-drops-upfront · decision · The three drop misalignments are refused at the top of apply_record, before the run context is loaded (phase 2)

`_check_drops(record, drops, run_id)` runs first in `apply_record`, so a drop passed with a `run_id` is refused before `_run_context` reads the run (a missing run would otherwise mask the real refusal), and the no-item / create-item checks need only the record's shape, not the matrix. The absent-ref refusal stays in `_acceptance_writes`, where `drop_levels` raises `AcceptanceError` inside the existing except and becomes `RecordRefusedError`; all refusals fire before the overlay is written. An extra test pins drop + addition re-pointing a row in one pass (spec §2.C).

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-09-26T00:58:49 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · _check_drops keeps only the last item per id, so the create refusal is decided by position (phase 2)

apply.py:568; create-then-move for one id would slip through. Verb records cannot reach it, so the risk was latent.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-09-26T00:58:49 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · A drop entry naming no refs passes every check and removes nothing (phase 2)

apply.py:556-579; {'target': {}} was a silent no-op.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-09-26T00:58:49 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · Refusal tests pinned only docs/acceptance, not HEAD or the tree; the run-id test matched a loose 'run' (phase 2)

test_record_apply.py:318 and :374.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-09-26T00:58:49 phase=2 state=open review_scope=out -->
### p2-r4 · finding [open] (reviewer: out of scope) · The engine accepts the same ref in the drops and in levels (drop then re-add) (phase 2)

Spec §2.B.3 and plan 03 put the contradiction refusal on the CLI; phase 3's Test Plan item 4 pins it. Defence-in-depth only.

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-09-26T00:58:49 phase=2 -->
### review-p2 · review · phase 2 code review: 4 minor findings (3 in scope, 1 out) (phase 2)

An independent reviewer reviewed 5823275f..7a9a6dfc against spec §2.B/§2.C and plan 02.yaml: 48 tests passed. Every refusal fires before any write, and create/move behaviour is unchanged when there are no drops. No critical or important issues. p2-r1 to p2-r3 are fixed; p2-r4 is out of scope (CLI-owned).

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-09-26T00:58:49 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: _check_drops keeps only the last item per id, so the create refusal is decided by position (phase 2)

_check_drops refuses a drop when the record names the row more than once; test_a_drop_on_a_row_the_record_names_twice_is_refused.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-09-26T00:58:49 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: A drop entry naming no refs passes every check and removes nothing (phase 2)

_check_drops refuses a drop entry with no refs; test_a_drop_entry_naming_no_refs_is_refused[no-levels|no-refs].

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-09-26T00:58:49 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: Refusal tests pinned only docs/acceptance, not HEAD or the tree; the run-id test matched a loose 'run' (phase 2)

Every refusal test now asserts HEAD and the full snapshot are unchanged; the run-id test matches 'verb-only'.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-09-26T00:58:49 phase=2 state=open resolves=p2-r4 out_of_scope=true -->
### p2-r4-resolved · finding [out-of-scope] · resolves p2-r4: The engine accepts the same ref in the drops and in levels (drop then re-add) (phase 2)

Spec §2.B.3 assigns the contradiction refusal to the CLI call. Phase 3 implements it and Test Plan item 4 pins it; this phase's engine contract is as specified.
