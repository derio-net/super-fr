# `vk plan rework` Command Surface Implementation Plan

## Phase 1: `**Track:**` parser, model, and writer plumbing

### Task 1: `Phase.track_label` model field

- P1.T1.S1: Write a failing test pinning the default-None behaviour

- P1.T1.S2: Add `track_label` to `Phase` with default `None`

- P1.T1.S3: Sweep for existing fixtures that build `Phase` positionally

### Task 2: Parser extraction of `**Track:**` body line

- P1.T2.S1: Write failing parser tests for ` Track:**`**

- P1.T2.S2: Add `_TRACK_RE` adjacent to `_DEPENDS_ON_RE`

- P1.T2.S3: Extract track in `_parse_phases` prelude slice

- P1.T2.S4: Re-run full parser suite to prove no regressions

### Task 3: Writer emits `**Track:**` after `**Depends on:**`

- P1.T3.S1: Write failing writer tests for Track emission

- P1.T3.S2: Emit ` Track:**` in `_write_phases`**

- P1.T3.S3: Full plan suite regression check

## Phase 2: `rework.py` core — template, numbering, Origin helpers

### Task 1: `next_rework_number` with cross-dir collision guard

- P2.T1.S1: Write failing tests for `next_rework_number`

- P2.T1.S2: Create `src/vk/plan/rework.py` with `next_rework_number`

### Task 2: Template constant and `render_scaffold()`

- P2.T2.S1: Write failing tests for `render_scaffold`

- P2.T2.S2: Add the template literal and `render_scaffold()` to `rework.py`

- P2.T2.S3: Pin the no-H1-fallback title path

### Task 3: `OriginRow` + `parse_origin_table`

- P2.T3.S1: Write the three Origin-table fixtures

- P2.T3.S2: Write failing tests for `parse_origin_table`

- P2.T3.S3: Implement `OriginRow` and `parse_origin_table`

### Task 4: `append_origin_row`

- P2.T4.S1: Write failing round-trip tests for `append_origin_row`

- P2.T4.S2: Implement `append_origin_row`

- P2.T4.S3: Full `test_rework.py` suite + whole-tree regression

## Phase 3: `vk plan rework` scaffold CLI

### Task 1: Typer command + happy-path integration test

- P3.T1.S1: Write the parent fixtures

- P3.T1.S2: Write a failing happy-path integration test

- P3.T1.S3: Add `scaffold_rework` orchestrator in `rework.py`

- P3.T1.S4: Register `vk plan rework` in `plan_cmd.py`

- P3.T1.S5: Stabilise repo_root discovery under tmp_path

### Task 2: Exit-code and warning matrix

- P3.T2.S1: Test — parent missing returns exit 2

- P3.T2.S2: Test — mis-located parent returns exit 2

- P3.T2.S3: Test — unarchived parent emits warning, proceeds

- P3.T2.S4: Test — rework-1 archived, rework-2 gets Prior rework line

- P3.T2.S5: Test — cross-dir collision exits 2

- P3.T2.S6: Test — no-H1 parent warns, uses fallback title

- P3.T2.S7: Full integration + unit regression

## Phase 4: `vk plan rework-add` CLI

### Task 1: Typer command with required flags

- P4.T1.S1: Write failing happy-path integration test

- P4.T1.S2: Register `vk plan rework-add`

### Task 2: Flag-validation and edge-case tests

- P4.T2.S1: Test — canonical tracks emit NO warn

- P4.T2.S2: Test — non-canonical track warns, still succeeds

- P4.T2.S3: Test — empty flag value exits 2 naming the flag

- P4.T2.S4: Test — newline in any flag exits 2

- P4.T2.S5: Test — pipe escape round-trips

- P4.T2.S6: Test — missing Origin section exits 2

- P4.T2.S7: Test — malformed Origin header exits 2

## Phase 5: `vk plan rework-list` CLI

### Task 1: Core glob + record assembly

- P5.T1.S1: Write failing test for empty repo

- P5.T1.S2: Implement `list_reworks` in `rework.py`

- P5.T1.S3: Register `vk plan rework-list` CLI

### Task 2: Filters and `--json`

- P5.T2.S1: Create `rework_with_phases.md` fixture

- P5.T2.S2: Test — two reworks list under default filters

- P5.T2.S3: Test — `--include-archived` picks up archived-plans

- P5.T2.S4: Test — `--status` filter case-insensitive exact match

- P5.T2.S5: Test — `--track decision` substring-matches `decision → development`

- P5.T2.S6: Test — `--plan` exact parent-slug match

- P5.T2.S7: Test — `--json` emits valid, non-empty JSON

- P5.T2.S8: Test — malformed file skipped with warn, others listed

## Phase 6: `self-review` canonical-Track-token lint

### Task 1: Extend `plan_self_review`

- P6.T1.S1: Write failing tests for the new lint branch

- P6.T1.S2: Insert the lint check inside `plan_self_review`

## Phase 7: Version bump, SKILL.md, release prep

### Task 1: Version bump across three source-of-truth files

- P7.T1.S1: Bump `pyproject.toml`

- P7.T1.S2: Bump `.claude-plugin/plugin.json`

- P7.T1.S3: Bump `.claude-plugin/marketplace.json`

- P7.T1.S4: Run `uv sync` to refresh `uv.lock`

- P7.T1.S5: Confirm `vk --version`

### Task 2: Update `skills/vk-plan/SKILL.md`

- P7.T2.S1: Add rework-surface mention under "Procedure" or "Integration"

### Task 3: Full-sweep CI gate + self-review

- P7.T3.S1: Run ruff format + check

- P7.T3.S2: Run mypy

- P7.T3.S3: Run full pytest

- P7.T3.S4: Self-review this plan file

- P7.T3.S5: `--help` smoke test
