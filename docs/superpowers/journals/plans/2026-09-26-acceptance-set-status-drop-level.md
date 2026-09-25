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
