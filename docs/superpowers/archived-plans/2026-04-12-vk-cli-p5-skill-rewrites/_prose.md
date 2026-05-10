# SKILL.md Rewrites + vk init + vk install-skills Implementation Plan

## Phase 1: Utility commands and skill validation tests

### Task 1: Skill validation test suite

- P1.T1.S1: Write the skill validation tests

- P1.T1.S2: Run tests to verify they pass against current SKILL.md files (except line limit)

- P1.T1.S3: Commit

### Task 2: `vk init` command

- P1.T2.S1: Write the failing test

- P1.T2.S2: Run test to verify it fails

- P1.T2.S3: Implement init_cmd.py

- P1.T2.S4: Wire init command into cli.py

- P1.T2.S5: Run tests and verify they pass

- P1.T2.S6: Run lint and type check

- P1.T2.S7: Commit

### Task 3: `vk install-skills` command

- P1.T3.S1: Write the failing test

- P1.T3.S2: Run test to verify it fails

- P1.T3.S3: Implement install_cmd.py

- P1.T3.S4: Wire install-skills command into cli.py

- P1.T3.S5: Run tests and verify they pass

- P1.T3.S6: Run lint and type check

- P1.T3.S7: Commit

### Task 4: Delete validate-skills.sh

- P1.T4.S1: Verify test_skill_validation.py covers all validate-skills.sh checks

- P1.T4.S2: Delete the bash script

- P1.T4.S3: Commit

## Phase 2: SKILL.md rewrites

### Task 1: Rewrite vk-dispatch/SKILL.md

- P2.T1.S1: Write the new vk-dispatch/SKILL.md

- P2.T1.S2: Run skill validation tests

- P2.T1.S3: Commit

### Task 2: Rewrite vk-plan/SKILL.md

- P2.T2.S1: Write the new vk-plan/SKILL.md

- P2.T2.S2: Run skill validation tests

- P2.T2.S3: Commit

### Task 3: Rewrite vk-progress/SKILL.md

- P2.T3.S1: Write the new vk-progress/SKILL.md

- P2.T3.S2: Run skill validation tests

- P2.T3.S3: Commit

### Task 4: Rewrite vk-execute/SKILL.md

- P2.T4.S1: Write the new vk-execute/SKILL.md

- P2.T4.S2: Run skill validation tests

- P2.T4.S3: Commit

### Task 5: Full validation and version bump

- P2.T5.S1: Run all skill validation tests

- P2.T5.S2: Run the full test suite

- P2.T5.S3: Run lint and type check

- P2.T5.S4: Bump version to 1.0.0

- P2.T5.S5: Commit

- P2.T5.S6: Run full suite one more time
