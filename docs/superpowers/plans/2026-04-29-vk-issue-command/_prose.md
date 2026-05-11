# vk issue command (Thread 4)

## Phase 1: `vk issue create` command

### Task 1: Tests for `vk issue create`

- P1.T1.S1: TDD — write failing tests for `create`

- P1.T1.S2: Run tests to confirm they fail

### Task 2: Implement `src/vk/commands/issue_cmd.py`

- P1.T2.S3: Create the module with `_build_issue_body` and `_resolve_repo`

### Task 3: Register in CLI

- P1.T3.S4: Register `issue_app` in `src/vk/cli.py`

- P1.T3.S5: Run all tests — no regressions

- P1.T3.S6: Smoke-test `vk issue create --dry-run`

## Phase 2: `vk issue convert` + version bump

### Task 1: Tests for `vk issue convert`

- P2.T1.S1: TDD — write failing tests for `convert`

- P2.T1.S2: Run tests to confirm they fail

### Task 2: Implement `vk issue convert`

- P2.T2.S3: Add `_build_contract_block()` helper and `convert` command

- P2.T2.S4: Run all tests

### Task 3: Version bump

- P2.T3.S5: Bump version in all three files

- P2.T3.S6: Run `uv sync` and confirm version

- P2.T3.S7: Run `vk plan self-review` on both plans

- P2.T3.S8: Update spec index for both plans
