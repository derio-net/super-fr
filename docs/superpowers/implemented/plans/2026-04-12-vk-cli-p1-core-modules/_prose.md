# VK CLI Core Modules Implementation Plan

## Phase 1: Config, models, format, and filename

### Task 1: Test fixtures — configs

- P1.T1.S1: Create all five config fixture files

- P1.T1.S2: Commit fixture files

### Task 2: Config module — Profile, PlanConfig, HeaderConfig, DispatchConfig

- P1.T2.S1: Write the failing tests

- P1.T2.S2: Run tests to verify they fail

- P1.T2.S3: Implement src/vk/config.py

- P1.T2.S4: Create src/vk/plan/__init__.py

- P1.T2.S5: Run tests to verify they pass

- P1.T2.S6: Commit

### Task 3: PlanFormat enum and detection

- P1.T3.S1: Write the failing tests

- P1.T3.S2: Run tests to verify they fail

- P1.T3.S3: Implement src/vk/plan/format.py

- P1.T3.S4: Run tests to verify they pass

- P1.T3.S5: Re-run config tests to verify format integration

- P1.T3.S6: Commit

### Task 4: Plan models — Plan, Phase, Task, Step, CheckboxState

- P1.T4.S1: Write the failing tests

- P1.T4.S2: Run tests to verify they fail

- P1.T4.S3: Implement src/vk/plan/models.py

- P1.T4.S4: Run tests to verify they pass

- P1.T4.S5: Commit

### Task 5: Filename slug derivation

- P1.T5.S1: Write the failing tests

- P1.T5.S2: Run tests to verify they fail

- P1.T5.S3: Implement src/vk/plan/filename.py

- P1.T5.S4: Run tests to verify they pass

- P1.T5.S5: Commit

- P1.T5.S6: Run full test suite

- P1.T5.S7: Run ruff and mypy

- P1.T5.S8: Commit any lint/type fixes if needed

## Phase 2: Parser, writer, and plan fixtures

### Task 1: Plan fixture files

- P2.T1.S1: Create phased-small.md fixture

- P2.T1.S2: Create phased-large.md fixture

- P2.T1.S3: Create phased-dispatched.md fixture

- P2.T1.S4: Create flat-small.md fixture

- P2.T1.S5: Create flat-mixed-tags.md fixture

- P2.T1.S6: Create not-a-plan.md fixture

- P2.T1.S7: Commit all plan fixtures

### Task 2: Plan parser — parse_plan() for both formats

- P2.T2.S1: Write the failing tests

- P2.T2.S2: Run tests to verify they fail

- P2.T2.S3: Implement src/vk/plan/parser.py

- P2.T2.S4: Run tests to verify they pass

- P2.T2.S5: Run ruff and mypy on new code

- P2.T2.S6: Commit

### Task 3: Plan writer — write_plan() with round-trip fidelity

- P2.T3.S1: Write the failing tests

- P2.T3.S2: Run tests to verify they fail

- P2.T3.S3: Implement src/vk/plan/writer.py

- P2.T3.S4: Run tests to verify they pass

- P2.T3.S5: Debug and fix round-trip mismatches

- P2.T3.S6: Commit

### Task 4: Spec fixture files

- P2.T4.S1: Create spec-with-index.md fixture

- P2.T4.S2: Create spec-without-index.md fixture

- P2.T4.S3: Commit spec fixtures

- P2.T4.S4: Run full test suite and quality gates

- P2.T4.S5: Commit any fixes

## Phase 3: Converter, spec index, git/gh helpers

### Task 1: Plan converter — to_flat, to_phased variants

- P3.T1.S1: Write the failing tests

- P3.T1.S2: Run tests to verify they fail

- P3.T1.S3: Implement src/vk/plan/convert.py

- P3.T1.S4: Run tests to verify they pass

- P3.T1.S5: Commit

### Task 2: Spec index — read/create/update implementation plans table

- P3.T2.S1: Write the failing tests

- P3.T2.S2: Run tests to verify they fail

- P3.T2.S3: Implement src/vk/spec_index.py

- P3.T2.S4: Run tests to verify they pass

- P3.T2.S5: Commit

### Task 3: Git helpers — subprocess wrappers

- P3.T3.S1: Write the failing tests

- P3.T3.S2: Run tests to verify they fail

- P3.T3.S3: Implement src/vk/git.py

- P3.T3.S4: Run tests to verify they pass

- P3.T3.S5: Commit

### Task 4: GitHub CLI helpers — subprocess wrappers

- P3.T4.S1: Write the failing tests

- P3.T4.S2: Run tests to verify they fail

- P3.T4.S3: Implement src/vk/gh.py

- P3.T4.S4: Run tests to verify they pass

- P3.T4.S5: Commit

### Task 5: Final quality gates and coverage check

- P3.T5.S1: Run full test suite with coverage

- P3.T5.S2: Run ruff lint and format check

- P3.T5.S3: Run mypy strict type checking

- P3.T5.S4: Fix any lint, format, or type errors

- P3.T5.S5: Commit fixes and verify clean
