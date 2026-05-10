# VK CLI Migration + Validation Sweep Implementation Plan

## Phase 1: Migration and validation sweep

### Task 1: Audit existing repos

- P1.T1.S1: Run the audit script

- P1.T1.S2: Record the audit results

### Task 2: Configure unconfigured repos

- P1.T2.S1: Run the init script

- P1.T2.S2: Verify the created configs

### Task 3: Verify dispatch-enabled repos

- P1.T3.S1: Check dispatch config fields

### Task 4: Test plan conversion for local-only repos

- P1.T4.S1: Find phased plans in local-only repos

- P1.T4.S2: Dry-run conversion for each identified plan

### Task 5: Replace old SKILL.md files

- P1.T5.S1: Remove old skill files and marketplace duplicates

- P1.T5.S2: Install vk CLI globally and reinstall skills

### Task 6: Smoke test

- P1.T6.S1: Run the smoke test script

### Task 7: Verify CI and re-enable dispatch

- P1.T7.S1: Push and verify CI in superpowers-for-vk

- P1.T7.S2: Re-enable dispatch for superpowers-for-vk
