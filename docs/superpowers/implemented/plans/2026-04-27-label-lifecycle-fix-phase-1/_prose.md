# Label Lifecycle Fix Phase 1 Implementation Plan

## Phase 1: Label registry and gh helpers

### Task 1: `src/vk/labels.py` registry

- P1.T1.S1: TDD — registry tests

- P1.T1.S2: Implement `src/vk/labels.py`

- P1.T1.S3: Run tests

### Task 2: `GhError` carries stderr and returncode

- P1.T2.S1: TDD — `GhError` carries fields

- P1.T2.S2: Extend `GhError` and `_run_gh`

- P1.T2.S3: Run tests

### Task 3: `gh.swap_issue_labels` helper

- P1.T3.S1: TDD — `swap_issue_labels`

- P1.T3.S2: Implement `swap_issue_labels`

- P1.T3.S3: Run tests

### Task 4: `is_transient` classifier and `with_retry` helper

- P1.T4.S1: TDD — classifier and retry

- P1.T4.S2: Implement classifier and retry

- P1.T4.S3: Run tests

### Task 5: Format, type-check, full unit suite, commit

- P1.T5.S1: Format and type-check

- P1.T5.S2: Full unit suite

- P1.T5.S3: Commit

## Phase 2: DispatchConfig defaults and dispatch reads registry

### Task 1: Extend `DispatchConfig.labels` defaults

- P2.T1.S1: TDD — defaults include new keys, user override merges

- P2.T1.S2: Update `DispatchConfig` and `_parse_dispatch`

- P2.T1.S3: Run tests

### Task 2: Dispatch bootstraps full registry with canonical colors

- P2.T2.S1: TDD — `ensure_labels` accepts `LabelDef`s

- P2.T2.S2: Update `gh.ensure_labels` signature

- P2.T2.S3: TDD — `dispatch create` builds full registry list

- P2.T2.S4: Update `dispatch_cmd.py`

- P2.T2.S5: Run tests

### Task 3: Format, type-check, full suite, commit

- P2.T3.S1: Format, type-check, full suite

- P2.T3.S2: Commit

## Phase 3: vk execute claim and pr-opened

### Task 1: `vk execute claim`

- P3.T1.S1: TDD — claim test cases

- P3.T1.S2: Implement `claim`

- P3.T1.S3: Run tests

### Task 2: `vk execute pr-opened`

- P3.T2.S1: TDD — pr-opened test cases

- P3.T2.S2: Implement `pr-opened`

- P3.T2.S3: Run tests

### Task 3: Format, type-check, full suite, commit

- P3.T3.S1: Format, type-check, full suite

- P3.T3.S2: Commit

## Phase 4: vk-execute skill update and version bump

### Task 1: Update `skills/vk-execute/SKILL.md`

- P4.T1.S1: TDD — skill validation asserts new shape

- P4.T1.S2: Update `skills/vk-execute/SKILL.md`

- P4.T1.S3: Run tests

### Task 2: Version bump

- P4.T2.S1: Confirm current version

- P4.T2.S2: Bump all three files to `1.3.0`

- P4.T2.S3: Refresh lockfile and confirm CLI

- P4.T2.S4: Format, type-check, full suite

- P4.T2.S5: Commit and PR
