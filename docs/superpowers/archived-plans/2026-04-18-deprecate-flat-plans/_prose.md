# Deprecate Flat Plans Implementation Plan

## Phase 1: Initial skill-doc rule change

### Task 1: Revise the PR-granularity rule

- P1.T1.S1: `vk-execute` constraint text. Change `One phase/task = one PR.` → `One phase = one PR.`; drop flat step-ID variant from the ID reference line.

- P1.T1.S2: `vk-execute` CLI arg placeholders. Replace `<phase-or-task>` → `<phase>` in the Procedure's `check-deps` / `scope` / `pr-body` commands.

- P1.T1.S3: `vk-execute` announce line. `implement this phase/task` → `implement this phase`.

- P1.T1.S4: Migration appendix (soft-deprecate). Add a `## Migrating flat plans` section pointing at the existing `vk plan convert --to phased` CLI with both `--single-phase` and `--group-by-tag` examples.

- P1.T1.S5: `vk-plan` description. Drop "or flat" from the frontmatter description.

- P1.T1.S6: `vk-plan` Format section. Rewrite so structure (phased) and routing (dispatch config) are independent concerns.

- P1.T1.S7: `vk-plan` execution handoff. Collapse the `Phased: …` / `Flat: …` fork into a single list gated on `plan-config.yaml`.

- P1.T1.S8: Verify tests. `uv run pytest tests/unit/test_skill_validation.py` — 27 passed, 9 skipped.

- P1.T1.S9: Commit.

## Phase 2: Strengthen to mandatory migration

### Task 1: Procedure step 0 in vk-execute

- P2.T1.S1: Replace lead sentence. Drop the "Flat plans are deprecated — see …" preamble; lead becomes `Implements a single phase from a plan.`

- P2.T1.S2: Insert Procedure step 0. Run `vk plan format <plan>`; if output is `flat`, run the Migration section before step 1. No alternative path.

- P2.T1.S3: Rewrite Migration section. Document two flows: **Automatic + review** (dry-run → convert → commit) and **Guided** (wrap via `--single-phase` then hand-edit to split at operator boundaries).

- P2.T1.S4: `vk-plan` Format section. Drop the soft "deprecated" sentence; point at the `vk-execute` Migration section for legacy plans.

- P2.T1.S5: `vk-dispatch` error row. Exit-2 row changes from "Suggest `vk plan convert …`" → "Run `vk plan convert …` and retry."

- P2.T1.S6: `vk-dispatch` integration bullet. "Convert flat to phased" → "Migrate legacy flat plans".

- P2.T1.S7: Verify tests. `uv run pytest tests/unit/test_skill_validation.py` — still 27 passed, 9 skipped.

- P2.T1.S8: Commit.

## Phase 3: CLI enforcement — close all flat escape hatches

### Task 1: `vk execute` guards

- P3.T1.S1: Introduce `_reject_flat(plan_path)` helper. Parses the plan and raises `typer.Exit(2)` with a copyable `vk plan convert` command if the shape is `FLAT`.

- P3.T1.S2: Call `_reject_flat` from all four sub-commands. `check-deps`, `scope`, `check-step`, `pr-body` — immediately after `plan_path.resolve()`.

- P3.T1.S3: Remove flat code paths. Drop `else:` branches in `check-deps`, `scope`, `pr-body`. Remove flat match from `_parse_step_id` (step IDs are now always `P<n>.T<n>.S<n>`). Simplify `_locate_task_slice` — phase_num is mandatory.

- P3.T1.S4: Clean help strings and docstrings. No more "(phased) or … (flat)" phrasing in CLI help; docstrings reflect phase-only model.

### Task 2: `vk plan format` dual-mode

- P3.T2.S1: Accept either a plan file or a repo root. File input: parse and print actual shape. Directory input: preserve legacy config-derived behavior.

- P3.T2.S2: Update docstring to explain that a `flat` result means the plan is a legacy artifact requiring migration.

### Task 3: `vk plan new` — phased by default

- P3.T3.S1: Unconditionally emit phased skeleton. Drop the `if profile.format.value == "phased"` branch — previously produced flat when dispatch was disabled, the exact coupling being removed.

### Task 4: `vk plan convert` — only `--to phased`

- P3.T4.S1: Reject `--to flat`. Emit error with exit 2 if any target other than `phased` is passed.

- P3.T4.S2: Drop `to_flat` import. The library function stays in `vk.plan.convert` (library tests retain coverage) but is no longer imported or called from the CLI.

- P3.T4.S3: Reframe docstring as "Migrate a legacy flat plan to phased format."

### Task 5: `vk dispatch` — sharpen error messages

- P3.T5.S1: Full migration command in `dispatch create`. Replace "Convert to phased first" with copy-pasteable `vk plan convert <plan> --to phased --single-phase --yes`.

- P3.T5.S2: Full migration command in `dispatch migrate`. Same treatment.

### Task 6: Tests

- P3.T6.S1: Add `phased_repo` fixture. Wraps `local_repo` through the migration converter. All `vk execute *` tests now use it.

- P3.T6.S2: Update 7 existing execute tests. Point at `phased_repo`; flip flat step IDs (`T1.S2`) to phased (`P1.T1.S2`); flip targets to phase numbers; rename `test_scope_prints_task` → `test_scope_prints_phase`.

- P3.T6.S3: Add `TestExecuteRejectsFlat` parametrised class. Covers all four execute sub-commands with exit-2 + `"vk plan convert"` substring assertions on flat input. Encodes the invariant.

- P3.T6.S4: `TestPlanFormat` gains file-path cases. Rename dir case to `test_format_directory_uses_config`; add flat-file case and phased-file case.

- P3.T6.S5: Verify full suite. `uv run pytest -q --no-cov` — 296 passed, 9 skipped.

- P3.T6.S6: Commit.

## Phase 4: Address code-review feedback

### Task 1: Fix I1 — `vk plan format` silently labeled missing paths as flat

- P4.T1.S1: Require `target.exists()`. A nonexistent path used to fall through to `load_profile()` which returned `FLAT` by default — misrouting agents. Now: explicit `typer.Exit(2)` with `"<path> does not exist."`

### Task 2: Fix I2 — uncaught tracebacks on non-plan files

- P4.T2.S1: Wrap `parse_plan` in `plan_format`. Catch `ValueError`; emit `"could not parse plan at <path>"` and exit 2.

- P4.T2.S2: Wrap `parse_plan` in `_reject_flat`. Catch both `FileNotFoundError` and `ValueError`; emit `"could not parse <path>"` and exit 2.

### Task 3: Fix M1 — drop ghost `--force` flag from `vk plan convert`

- P4.T3.S1: Remove the typer Option. Flag had no effect on any supported target (`to_flat` is the only consumer and is gone from the CLI). Also removed the `_ = force` placeholder.

- P4.T3.S2: Trim the docstring accordingly.

### Task 4: Fix M2 — consistent migration hints

- P4.T4.S1: `dispatch migrate` error. Add the full `--to phased --single-phase --yes` invocation (was missing the strategy flag).

- P4.T4.S2: `vk-dispatch` error row. Same — include the strategy flag so copying the command works first try.

### Task 5: Fix M5 + M6 — skill polish

- P4.T5.S1: M5 — frontmatter description. `"Execute an agentic phase or task from a plan."` → `"Execute an agentic phase from a plan."`

- P4.T5.S2: M6 — Constraints bullet. Add `- Migration (if needed) is a separate PR from any phase.` so agents skimming Constraints see the rule.

### Task 6: Regression tests for the guards

- P4.T6.S1: `test_format_missing_path_errors`. Exit 2; "does not exist" in output.

- P4.T6.S2: `test_format_non_plan_file_errors`. Exit 2; "could not parse" in output.

- P4.T6.S3: `test_non_plan_file_errors_cleanly`. Parametrised across all four execute sub-commands; asserts exit 2 and "could not parse" surfaces (no traceback).

- P4.T6.S4: Verify full suite. `uv run pytest -q --no-cov` — 302 passed, 9 skipped.

- P4.T6.S5: Commit.

## Phase 5: Make CI green

### Task 1: Unblock CI

- P5.T1.S1: Diagnose. `gh pr checks 21` → lint fails. `gh run view … --log-failed` → `ruff format --check` wants three files reformatted. Tests and typecheck pass.

- P5.T1.S2: Run `uv run ruff format src/ tests/`. Three files reformatted (whitespace collapsing around tuple/call sites). No behavior change.

- P5.T1.S3: Re-verify. Full suite still 302 passed; `ruff format --check` clean; `ruff check` clean.

- P5.T1.S4: Commit.
