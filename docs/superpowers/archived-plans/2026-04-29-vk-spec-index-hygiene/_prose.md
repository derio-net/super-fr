# vk spec-index hygiene (Threads 1a + 1b + 2)

## Phase 1: Fix `spec_index.py` — path-based upsert + prose preservation

### Task 1: Tests for `spec_index.py` fixes

- P1.T1.S1: TDD — write failing tests

- P1.T1.S2: Run tests to confirm they fail before the fix

### Task 2: Fix `spec_index.py`

- P1.T2.S3: Fix `upsert_entry()` — match by file path

- P1.T2.S4: Fix `upsert_entry()` — replace only the table block, preserve trailing prose

- P1.T2.S5: Fix `_build_table()` — guard backticks on non-path File values

- P1.T2.S6: Run all new tests — must pass

- P1.T2.S7: Run full test suite — no regressions

## Phase 2: Fix `progress_cmd.py` — column preservation + path-based lookup

### Task 1: Tests for `_reconcile_spec_index` column preservation

- P2.T1.S1: TDD — write failing tests

- P2.T1.S2: Run tests to confirm they fail before the fix

### Task 2: Fix `progress_cmd.py`

- P2.T2.S3: Update `_reconcile_spec_index()` signature

- P2.T2.S4: Rewrite lookup and entry-building in `_reconcile_spec_index()`

- P2.T2.S5: Update archive-rename call site in `sync()`

- P2.T2.S6: Fix `transition` command — read existing entry before building IndexEntry

- P2.T2.S7: Run all tests — no regressions

## Phase 3: Add `target_repo` to Phase model + parser + self-review check

### Task 1: Tests for multi-repo warning

- P3.T1.S1: TDD — write failing tests

- P3.T1.S2: Run tests to confirm they fail

### Task 2: Add `target_repo` to Phase model

- P3.T2.S3: Add `target_repo: str | None = None` to `Phase`

### Task 3: Update parser to extract `**Target repo:**`

- P3.T3.S4: Add regex and extraction

### Task 4: Add multi-repo check to `plan_self_review()`

- P3.T4.S5: Add check after Track-label lint in `plan_self_review()`

- P3.T4.S6: Run all tests

- P3.T4.S7: Run `vk plan self-review` on this plan to confirm it passes
