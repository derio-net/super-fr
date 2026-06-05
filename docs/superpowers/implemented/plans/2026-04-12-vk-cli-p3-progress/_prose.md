# VK Progress Commands Implementation Plan

## Phase 1: Progress command scaffold and sync

### Task 1: Test fixtures for progress commands

- P1.T1.S1: Create flat plan fixture with mixed checkbox states

- P1.T1.S2: Create phased plan fixture with partial progress

- P1.T1.S3: Create dispatch-enabled config fixture for progress tests

- P1.T1.S4: Create integration test conftest with tmp_git_repo fixture

- P1.T1.S5: Run tests to confirm fixtures load

- P1.T1.S6: Commit

### Task 2: progress sync subcommand — local mode

- P1.T2.S1: Write failing tests for local-mode sync

- P1.T2.S2: Run tests to verify they fail

- P1.T2.S3: Create progress_cmd.py with sync subcommand (local mode)

- P1.T2.S4: Wire progress_app into cli.py

- P1.T2.S5: Run tests to verify local-mode sync passes

- P1.T2.S6: Commit

### Task 3: progress sync — dispatch mode

- P1.T3.S1: Write failing tests for dispatch-mode sync

- P1.T3.S2: Run tests to verify they fail

- P1.T3.S3: Implement dispatch-mode sync logic

- P1.T3.S4: Run tests to verify dispatch-mode sync passes

- P1.T3.S5: Commit

### Task 4: progress board subcommand

- P1.T4.S1: Write failing tests for board — both modes

- P1.T4.S2: Run tests to verify they fail

- P1.T4.S3: Implement board subcommand

- P1.T4.S4: Run tests to verify board passes

- P1.T4.S5: Commit

### Task 5: progress create subcommand

- P1.T5.S1: Write failing tests for create — both modes

- P1.T5.S2: Run tests to verify they fail

- P1.T5.S3: Implement create subcommand

- P1.T5.S4: Run tests to verify create passes

- P1.T5.S5: Commit

### Task 6: progress transition subcommand

- P1.T6.S1: Write failing tests for transition — both modes

- P1.T6.S2: Run tests to verify they fail

- P1.T6.S3: Implement transition subcommand

- P1.T6.S4: Run tests to verify transition passes

- P1.T6.S5: Commit

### Task 7: progress audit subcommand

- P1.T7.S1: Write failing tests for audit — both modes

- P1.T7.S2: Run tests to verify they fail

- P1.T7.S3: Implement audit subcommand

- P1.T7.S4: Run tests to verify audit passes

- P1.T7.S5: Run full progress test suite

- P1.T7.S6: Run quality gates

- P1.T7.S7: Commit
