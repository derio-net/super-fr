# Lossless Plan Convert Implementation Plan

## Phase 1: Loose step-header regex tolerates trailing prose

### Task 1: Tolerate trailing prose after `**Step N: title**`

- P1.T1.S1: Add failing fixture and test case for loose-format steps.

- P1.T1.S2: Loosen `_RE_STEP` to absorb trailing prose into the title.

- P1.T1.S3: Verify `test_plan_loose_format.py::TestLooseStepHeaders` passes and all 58 pre-existing plan tests still pass.

## Phase 2: `**Files:**` verb preservation

### Task 1: Capture and re-emit the file-mention verb

- P2.T1.S1: Add failing round-trip test for verb preservation.

- P2.T1.S2: Add `file_mention_verbs: tuple[str, ...] = ()` to `Task`.

- P2.T1.S3: Promote `_RE_FILE_MENTION` group 1 to capture the verb; update `_parse_files` to return `list[tuple[str, str]]`.

- P2.T1.S4: Update `_write_tasks` in `writer.py` to zip verbs with paths.

- P2.T1.S5: Propagate `file_mention_verbs` through all three converters in `convert.py` (`to_flat`, `to_phased_one_per_task`, `_renumber_tasks`).

- P2.T1.S6: Re-run the full plan test suite and the round-trip test.

## Phase 3: `Plan.preamble` captures free-form header content

### Task 1: Add a `preamble` field and wire it through parse/write/convert

- P3.T1.S1: Add failing tests for Architecture + Tech Stack survival.

- P3.T1.S2: Add `preamble: str = ""` as the final field on `Plan`.

- P3.T1.S3: Implement `_extract_preamble(text)` in `parser.py`.

- P3.T1.S4: Populate `preamble` in both `Plan` construction sites in `parse_plan`.

- P3.T1.S5: Emit the preamble in `_write_header` between ` Goal:**` and the `---` divider.**

- P3.T1.S6: Propagate `preamble=plan.preamble` through all four `Plan(...)` constructions in `convert.py`.

- P3.T1.S7: Confirm on a real kid-laptops plan.

## Phase 4: Dotted step labels (`Step 0.1`, `Step 1.10`)

### Task 1: Accept dotted step labels while keeping `number: int` for existing callers

- P4.T1.S1: Extend fixture with a `Task 2` using `Step 0.1` / `Step 0.2` labels.

- P4.T1.S2: Add `label: str | None = None` to `Step`.

- P4.T1.S3: Change `_RE_STEP`'s number group to `(\d+(?:\.\d+)*)` and update `_parse_steps` to derive `number` / `label`.

- P4.T1.S4: Update `_write_steps` to prefer `label` when present.

- P4.T1.S5: Verify against kid-laptops plan 8.

- P4.T1.S6: Commit phases 1–4 together and run the full suite.

## Phase 5: Preserve step-body indentation on parse

### Task 1: Replace `strip()` with `textwrap.dedent(...).rstrip()`

- P5.T1.S1: Write the failing test first.

- P5.T1.S2: Import `textwrap` and swap `.strip()` for `dedent().rstrip()` in `_parse_steps`.

- P5.T1.S3: Re-run the full plan test suite — confirm the new test goes green and no existing test regresses.

- P5.T1.S4: Verify end-to-end against kid-laptops plan 7.

- P5.T1.S5: Commit on the same `fix/plan-convert-content-loss` branch.

- P5.T1.S6: Update this plan — mark phase 5 steps `[x]` and set ` Status:** Complete`.**
