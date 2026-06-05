# Dispatch Ensure Labels Implementation Plan

## Phase 1: `ensure_label` / `ensure_labels` in `vk.gh`

### Task 1: Helpers + unit tests

- P1.T1.S1: TDD — add `TestEnsureLabel` and `TestEnsureLabels`

- P1.T1.S2: Implement `ensure_label` and `ensure_labels`

- P1.T1.S3: Run unit tests

## Phase 2: Call `ensure_labels` from `dispatch create`

### Task 1: Bootstrap labels once before the creation loop

- P2.T1.S1: TDD — integration tests

- P2.T1.S2: Wire the call

- P2.T1.S3: Run

## Phase 3: Call `ensure_labels` from `dispatch migrate`

### Task 1: Group by repo and ensure labels per repo

- P3.T1.S1: TDD — integration tests

- P3.T1.S2: Wire the call

- P3.T1.S3: Run

## Phase 4: Bump version and run full suite
