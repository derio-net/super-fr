# VK CLI Dispatch Command Implementation Plan

## Phase 1: Dispatch command and shared CLI helpers

### Task 1: Shared CLI helpers (`common.py`)

- P1.T1.S1: Write the failing tests for tri-state flag validation and confirmation prompt

- P1.T1.S2: Run tests to verify they fail

- P1.T1.S3: Implement `common.py`

- P1.T1.S4: Run tests to verify they pass

- P1.T1.S5: Run quality gates

- P1.T1.S6: Commit

### Task 2: gh contract tests (`test_gh.py`)

- P1.T2.S1: Write the contract tests for gh subprocess calls

- P1.T2.S2: Run tests to verify they fail

- P1.T2.S3: Extend `src/vk/gh.py` with the dispatch-facing functions

- P1.T2.S4: Run contract tests to verify they pass

- P1.T2.S5: Run quality gates

- P1.T2.S6: Commit

### Task 3: Dispatch command core logic (`dispatch_cmd.py`)

- P1.T3.S1: Write failing integration test for dry-run output

- P1.T3.S2: Run tests to verify they fail

- P1.T3.S3: Implement `dispatch_cmd.py`

- P1.T3.S4: Wire dispatch into `cli.py`

- P1.T3.S5: Run integration tests

- P1.T3.S6: Run full test suite

- P1.T3.S7: Run quality gates

- P1.T3.S8: Commit

### Task 4: Dispatch exit code coverage and edge cases

- P1.T4.S1: Write failing tests for remaining exit codes and edge cases

- P1.T4.S2: Run new tests to verify they fail (for genuinely new assertions)

- P1.T4.S3: Fix any failing edge case handling in `dispatch_cmd.py`

- P1.T4.S4: Run full test suite

- P1.T4.S5: Commit

### Task 5: Spec index update after dispatch

- P1.T5.S1: Write failing test for spec index update

- P1.T5.S2: Run test to verify it fails

- P1.T5.S3: Verify spec index update is wired into dispatch flow

- P1.T5.S4: Run test to verify it passes

- P1.T5.S5: Run full test suite

- P1.T5.S6: Commit

### Task 6: Version bump and final validation

- P1.T6.S1: Update version test expectation

- P1.T6.S2: Run test to verify it fails

- P1.T6.S3: Bump version in pyproject.toml and __init__.py

- P1.T6.S4: Run full test suite

- P1.T6.S5: Run all quality gates

- P1.T6.S6: Commit
