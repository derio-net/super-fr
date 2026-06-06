# Label Lifecycle Fix Phase 3 Implementation Plan: `vk admin labels-sync`

## Phase 1: gh helpers, admin module skeleton, repo enumeration

### Task 1: New `gh.py` helpers

- P1.T1.S1: TDD — `list_labels`, `list_repos`, `delete_label`

- P1.T1.S2: Implement `list_labels`, `list_repos`, `delete_label`

- P1.T1.S3: Run tests

### Task 2: `vk admin` skeleton

- P1.T2.S1: Create `admin_cmd.py` skeleton

- P1.T2.S2: Wire into `main.py`

- P1.T2.S3: Skeleton-level tests

- P1.T2.S4: Run tests

### Task 3: Repo enumeration logic

- P1.T3.S1: TDD — `_resolve_target_repos`

- P1.T3.S2: Implement `_resolve_target_repos`

- P1.T3.S3: Run tests

### Task 4: Format, type-check, full suite, commit

- P1.T4.S1: Format and type-check

- P1.T4.S2: Full suite

- P1.T4.S3: Commit and PR

## Phase 2: Diff logic, dry-run rendering, default-label removal logic

### Task 1: `_diff_labels` — compute action buckets

- P2.T1.S1: TDD — `_diff_labels` cases

- P2.T1.S2: Implement `_diff_labels` + `LabelAction`

- P2.T1.S3: Run tests

### Task 2: `_default_label_actions` — `--remove-defaults` with safety guard

- P2.T2.S1: TDD — `gh.count_issues_with_label`

- P2.T2.S2: Implement `gh.count_issues_with_label`

- P2.T2.S3: TDD — `_default_label_actions`

- P2.T2.S4: Implement `DEFAULT_LABELS` + `_default_label_actions`

- P2.T2.S5: Run tests

### Task 3: Dry-run rendering

- P2.T3.S1: TDD — dry-run table rows match action buckets

- P2.T3.S2: Implement `_render_dryrun_table` + wire into `labels_sync`

- P2.T3.S3: Run tests

### Task 4: Format, type-check, full suite, commit

- P2.T4.S1: Format, type-check

- P2.T4.S2: Full suite

- P2.T4.S3: Commit and PR

## Phase 3: Apply mode and version bump

### Task 1: Apply mode

- P3.T1.S1: TDD — apply mode invokes correct gh calls

- P3.T1.S2: Implement apply mode

- P3.T1.S3: Run tests

### Task 2: Format, type-check, full suite

- P3.T2.S1: Format, type-check

- P3.T2.S2: Full suite

### Task 3: Version bump

- P3.T3.S1: Confirm current version

- P3.T3.S2: Bump (minor)

- P3.T3.S3: Refresh lockfile

- P3.T3.S4: Final test run

- P3.T3.S5: Commit and PR
