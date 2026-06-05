# Plugin Canonical Skills Implementation Plan

## Phase 0: Canonical Skills Rewrite

### Task 1: Rewrite vk-plan as standalone canonical skill

- P0.T1.S1: Replace skills/vk-plan/SKILL.md with the new standalone version

### Task 1: <component>

- P0.T1.S1: Write the failing test

- P0.T1.S5: Commit

### Task 2: <component>

- P0.T2.S1: Write the failing test

- P0.T2.S2: Run test to verify it fails

- P0.T2.S3: Write minimal implementation

- P0.T2.S4: Run test to verify it passes

- P0.T2.S5: Commit

- P0.T2.S2: Verify the new skill

- P0.T2.S3: Commit

### Task 2: Add profile reading to vk-dispatch

- P0.T2.S1: Add Profile Reading section

- P0.T2.S2: Replace hardcoded values with profile variables

- P0.T2.S3: Update frontmatter description

- P0.T2.S4: Verify

- P0.T2.S5: Commit

### Task 3: Rewrite vk-progress to absorb work-lifecycle

- P0.T3.S1: Replace skills/vk-progress/SKILL.md with the expanded version

- P0.T3.S2: Verify

- P0.T3.S3: Commit

### Task 4: Update vk-execute for Phase > Task > Step hierarchy

- P0.T4.S1: Update the description and procedure

- P0.T4.S2: Verify

- P0.T4.S3: Commit

## Phase 1: Plugin Infrastructure

### Task 1: Create plan-config.yaml for superpowers-for-vk

- P1.T1.S1: Write the minimal profile

- P1.T1.S2: Verify YAML

- P1.T1.S3: Commit

### Task 2: Create canonical validator script

- P1.T2.S1: Write the validator

- P1.T2.S2: Make executable and test

- P1.T2.S3: Commit

### Task 3: Create install script and vk-plan override rule

- P1.T3.S1: Create the rule

- P1.T3.S2: Write the install script

- P1.T3.S3: Make executable and verify

- P1.T3.S4: Commit

### Task 4: Update README and bump version to 0.2.0

- P1.T4.S1: Replace README.md

- P1.T4.S2: Bump version

- P1.T4.S3: Verify versions match

- P1.T4.S4: Commit

## Phase 2: Plan-file safety hardening

### Task 1: Add "Embedding Full File Content" section to vk-plan SKILL.md

- P2.T1.S1: Insert the new section between "No Placeholders" and "Plan Document Header"

- P2.T1.S2: Verify the section is in place

- P2.T1.S3: Commit

### Task 2: Create validate-skills.sh

- P2.T2.S1: Write the validator

- P2.T2.S2: Make executable and test
