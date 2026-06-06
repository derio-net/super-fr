# Label Lifecycle Fix Phase 2 Implementation Plan: Project-Board Excision

## Phase 1: Drop dead gh helpers, config field, dispatch flag, scaffold refs

### Task 1: Delete dead helpers from `src/vk/gh.py`

- P1.T1.S1: Identify deletion targets via grep

- P1.T1.S2: Delete the six functions

- P1.T1.S3: Delete `add_to_project` test from `tests/unit/test_gh.py`

- P1.T1.S4: Run unit tests

### Task 2: Drop `project_board` from `DispatchConfig` and `_parse_dispatch`

- P1.T2.S1: TDD — assert field absence

- P1.T2.S2: Drop the field

- P1.T2.S3: Run tests

### Task 3: Drop `--project` flag from `vk dispatch`

- P1.T3.S1: Locate references

- P1.T3.S2: Remove the flag and the discard

- P1.T3.S3: Confirm tests still pass

### Task 4: Update scaffold (`init_cmd.py`, `common.py`)

- P1.T4.S1: Update `init_cmd.py` YAML scaffold

- P1.T4.S2: Update `common.py` scaffold docstring

- P1.T4.S3: Update `test_common.py`

- P1.T4.S4: Run tests

### Task 5: Update fixtures

- P1.T5.S1: Drop `project_board` from `conftest.py:62`

- P1.T5.S2: Drop `project_board` from the fixture YAML

- P1.T5.S3: Run integration tests

### Task 6: Format, type-check, full suite, commit

- P1.T6.S1: Format and type-check

- P1.T6.S2: Full unit + integration suite

- P1.T6.S3: Commit and PR

## Phase 2: Drop dispatch-mode progress features and version bump

### Task 1: Delete `_run_dispatch_audit` and its callees

- P2.T1.S1: Delete the audit's dispatch-mode block

- P2.T1.S2: Delete `get_project_number`, `list_project_items`, `BoardItem`

- P2.T1.S3: Delete board-mocking tests in `test_audit.py`

- P2.T1.S4: Run tests

### Task 2: Drop `vk progress create --lifecycle`

- P2.T2.S1: Drop the flag and its body emission

- P2.T2.S2: Confirm no tests invoke `--lifecycle`

- P2.T2.S3: Run tests

### Task 3: Drop `vk progress transition` dispatch branch

- P2.T3.S1: Replace dispatch branch with explicit gate

- P2.T3.S2: Update tests if needed

### Task 4: Format, type-check, full suite

- P2.T4.S1: Format, type-check

- P2.T4.S2: Full suite

### Task 5: Version bump

- P2.T5.S1: Confirm current version

- P2.T5.S2: Bump all three files (patch)

- P2.T5.S3: Refresh lockfile

- P2.T5.S4: Final test run

- P2.T5.S5: Commit and PR
