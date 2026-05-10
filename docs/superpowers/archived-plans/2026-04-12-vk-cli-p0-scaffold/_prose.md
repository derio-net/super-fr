# VK CLI Scaffolding Implementation Plan

## Phase 1: Project skeleton

### Task 1: pyproject.toml and package init

- P1.T1.S1: Write the failing test

- P1.T1.S2: Run test to verify it fails

- P1.T1.S3: Create pyproject.toml

- P1.T1.S4: Create src/vk/__init__.py

- P1.T1.S5: Create src/vk/__main__.py

- P1.T1.S6: Run uv sync and verify test passes

- P1.T1.S7: Commit

### Task 2: CLI app with stub subcommands

- P1.T2.S1: Write the failing test

- P1.T2.S2: Run test to verify it fails

- P1.T2.S3: Write src/vk/cli.py

- P1.T2.S4: Create src/vk/commands/__init__.py

- P1.T2.S5: Run tests

- P1.T2.S6: Run full suite with coverage

- P1.T2.S7: Commit

### Task 3: CI workflow and quality gates

- P1.T3.S1: Create tests/conftest.py

- P1.T3.S2: Create .github/workflows/ci.yml

- P1.T3.S3: Run lint locally

- P1.T3.S4: Run mypy locally

- P1.T3.S5: Run full test suite

- P1.T3.S6: Commit

- P1.T3.S7: Generate uv.lock and final commit
