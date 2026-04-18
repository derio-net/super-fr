# Deprecate Flat Plans Implementation Plan

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-18-deprecate-flat-plans-design.md`
**Status:** In Progress

**Goal:** Retire flat plans as a supported shape across skills and CLI. Require migration on encounter; keep library-level parsing support so legacy plans can be read for migration.

**Architecture:** Three SKILL.md files (`vk-execute`, `vk-plan`, `vk-dispatch`) lose all flat-as-option language and grow a mandatory Procedure step 0 migration check. CLI commands (`vk execute *`, `vk plan new`, `vk plan convert`, `vk plan format`, `vk dispatch`) add a `_reject_flat` guard, collapse dual code paths, and surface copyable migration commands on flat input. Library internals (`vk.plan.{parser, convert, models, format}`) stay bilingual so migration still reads legacy input.

**Tech Stack:** Python 3.11+, uv, typer, ruff, pytest.

---

> Retrospective plan — the work was implemented and reviewed as PR [derio-net/superpowers-for-vk#21](https://github.com/derio-net/superpowers-for-vk/pull/21) before this plan was written. Each phase corresponds to one commit on the `deprecate-flat-plans` branch, in chronological order. All steps below are marked `[x]` because the work is done.

## Phase 1: Initial skill-doc rule change [agentic]

Commit `71a5cd4` — *docs(skills): deprecate flat plans — one phase = one PR*.

### Task 1: Revise the PR-granularity rule

**Files:**
- Modify: `skills/vk-execute/SKILL.md`
- Modify: `skills/vk-plan/SKILL.md`

- [x] **Step 1: `vk-execute` constraint text.** Change `One phase/task = one PR.` → `One phase = one PR.`; drop flat step-ID variant from the ID reference line.
- [x] **Step 2: `vk-execute` CLI arg placeholders.** Replace `<phase-or-task>` → `<phase>` in the Procedure's `check-deps` / `scope` / `pr-body` commands.
- [x] **Step 3: `vk-execute` announce line.** `implement this phase/task` → `implement this phase`.
- [x] **Step 4: Migration appendix (soft-deprecate).** Add a `## Migrating flat plans` section pointing at the existing `vk plan convert --to phased` CLI with both `--single-phase` and `--group-by-tag` examples.
- [x] **Step 5: `vk-plan` description.** Drop "or flat" from the frontmatter description.
- [x] **Step 6: `vk-plan` Format section.** Rewrite so structure (phased) and routing (dispatch config) are independent concerns.
- [x] **Step 7: `vk-plan` execution handoff.** Collapse the `Phased: …` / `Flat: …` fork into a single list gated on `plan-config.yaml`.
- [x] **Step 8: Verify tests.** `uv run pytest tests/unit/test_skill_validation.py` — 27 passed, 9 skipped.
- [x] **Step 9: Commit.**

## Phase 2: Strengthen to mandatory migration [agentic]

Commit `c38fc50` — *docs(skills): mandate migration; drop 'deprecated' framing*.

Scope shift driven by operator directive: "remove all flat references and instead offer automatic migration … no alternative to migration … migration can be automatic+review or guided."

### Task 1: Procedure step 0 in vk-execute

**Files:**
- Modify: `skills/vk-execute/SKILL.md`
- Modify: `skills/vk-plan/SKILL.md`
- Modify: `skills/vk-dispatch/SKILL.md`

- [x] **Step 1: Replace lead sentence.** Drop the "Flat plans are deprecated — see …" preamble; lead becomes `Implements a single phase from a plan.`
- [x] **Step 2: Insert Procedure step 0.** Run `vk plan format <plan>`; if output is `flat`, run the Migration section before step 1. No alternative path.
- [x] **Step 3: Rewrite Migration section.** Document two flows: **Automatic + review** (dry-run → convert → commit) and **Guided** (wrap via `--single-phase` then hand-edit to split at operator boundaries).
- [x] **Step 4: `vk-plan` Format section.** Drop the soft "deprecated" sentence; point at the `vk-execute` Migration section for legacy plans.
- [x] **Step 5: `vk-dispatch` error row.** Exit-2 row changes from "Suggest `vk plan convert …`" → "Run `vk plan convert …` and retry."
- [x] **Step 6: `vk-dispatch` integration bullet.** "Convert flat to phased" → "Migrate legacy flat plans".
- [x] **Step 7: Verify tests.** `uv run pytest tests/unit/test_skill_validation.py` — still 27 passed, 9 skipped.
- [x] **Step 8: Commit.**

## Phase 3: CLI enforcement — close all flat escape hatches [agentic]

Commit `cef82a6` — *feat(cli): enforce phased plans; close all flat escape hatches*.

### Task 1: `vk execute` guards

**Files:**
- Modify: `src/vk/commands/execute_cmd.py`

- [x] **Step 1: Introduce `_reject_flat(plan_path)` helper.** Parses the plan and raises `typer.Exit(2)` with a copyable `vk plan convert` command if the shape is `FLAT`.
- [x] **Step 2: Call `_reject_flat` from all four sub-commands.** `check-deps`, `scope`, `check-step`, `pr-body` — immediately after `plan_path.resolve()`.
- [x] **Step 3: Remove flat code paths.** Drop `else:` branches in `check-deps`, `scope`, `pr-body`. Remove flat match from `_parse_step_id` (step IDs are now always `P<n>.T<n>.S<n>`). Simplify `_locate_task_slice` — phase_num is mandatory.
- [x] **Step 4: Clean help strings and docstrings.** No more "(phased) or … (flat)" phrasing in CLI help; docstrings reflect phase-only model.

### Task 2: `vk plan format` dual-mode

**Files:**
- Modify: `src/vk/commands/plan_cmd.py`

- [x] **Step 1: Accept either a plan file or a repo root.** File input: parse and print actual shape. Directory input: preserve legacy config-derived behavior.
- [x] **Step 2: Update docstring** to explain that a `flat` result means the plan is a legacy artifact requiring migration.

### Task 3: `vk plan new` — phased by default

**Files:**
- Modify: `src/vk/commands/plan_cmd.py`

- [x] **Step 1: Unconditionally emit phased skeleton.** Drop the `if profile.format.value == "phased"` branch — previously produced flat when dispatch was disabled, the exact coupling being removed.

### Task 4: `vk plan convert` — only `--to phased`

**Files:**
- Modify: `src/vk/commands/plan_cmd.py`

- [x] **Step 1: Reject `--to flat`.** Emit error with exit 2 if any target other than `phased` is passed.
- [x] **Step 2: Drop `to_flat` import.** The library function stays in `vk.plan.convert` (library tests retain coverage) but is no longer imported or called from the CLI.
- [x] **Step 3: Reframe docstring** as "Migrate a legacy flat plan to phased format."

### Task 5: `vk dispatch` — sharpen error messages

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py`

- [x] **Step 1: Full migration command in `dispatch create`.** Replace "Convert to phased first" with copy-pasteable `vk plan convert <plan> --to phased --single-phase --yes`.
- [x] **Step 2: Full migration command in `dispatch migrate`.** Same treatment.

### Task 6: Tests

**Files:**
- Modify: `tests/integration/test_plan_execute.py`

- [x] **Step 1: Add `phased_repo` fixture.** Wraps `local_repo` through the migration converter. All `vk execute *` tests now use it.
- [x] **Step 2: Update 7 existing execute tests.** Point at `phased_repo`; flip flat step IDs (`T1.S2`) to phased (`P1.T1.S2`); flip targets to phase numbers; rename `test_scope_prints_task` → `test_scope_prints_phase`.
- [x] **Step 3: Add `TestExecuteRejectsFlat` parametrised class.** Covers all four execute sub-commands with exit-2 + `"vk plan convert"` substring assertions on flat input. Encodes the invariant.
- [x] **Step 4: `TestPlanFormat` gains file-path cases.** Rename dir case to `test_format_directory_uses_config`; add flat-file case and phased-file case.
- [x] **Step 5: Verify full suite.** `uv run pytest -q --no-cov` — 296 passed, 9 skipped.
- [x] **Step 6: Commit.**

## Phase 4: Address code-review feedback [agentic]

Commit `a256d13` — *fix: address code review — harden format guards, drop ghost flag*.

Dispatched `superpowers:code-reviewer` subagent against the branch before merge. Findings: no Critical; two Important (I1, I2); six Minor (M1–M6). Applied I1, I2, M1, M2, M5, M6. Deferred M3 (double-parse refactor) and M4 (registry-bound parametrisation) as follow-ups.

### Task 1: Fix I1 — `vk plan format` silently labeled missing paths as flat

**Files:**
- Modify: `src/vk/commands/plan_cmd.py`

- [x] **Step 1: Require `target.exists()`.** A nonexistent path used to fall through to `load_profile()` which returned `FLAT` by default — misrouting agents. Now: explicit `typer.Exit(2)` with `"<path> does not exist."`

### Task 2: Fix I2 — uncaught tracebacks on non-plan files

**Files:**
- Modify: `src/vk/commands/plan_cmd.py`
- Modify: `src/vk/commands/execute_cmd.py`

- [x] **Step 1: Wrap `parse_plan` in `plan_format`.** Catch `ValueError`; emit `"could not parse plan at <path>"` and exit 2.
- [x] **Step 2: Wrap `parse_plan` in `_reject_flat`.** Catch both `FileNotFoundError` and `ValueError`; emit `"could not parse <path>"` and exit 2.

### Task 3: Fix M1 — drop ghost `--force` flag from `vk plan convert`

**Files:**
- Modify: `src/vk/commands/plan_cmd.py`

- [x] **Step 1: Remove the typer Option.** Flag had no effect on any supported target (`to_flat` is the only consumer and is gone from the CLI). Also removed the `_ = force` placeholder.
- [x] **Step 2: Trim the docstring** accordingly.

### Task 4: Fix M2 — consistent migration hints

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py`
- Modify: `skills/vk-dispatch/SKILL.md`

- [x] **Step 1: `dispatch migrate` error.** Add the full `--to phased --single-phase --yes` invocation (was missing the strategy flag).
- [x] **Step 2: `vk-dispatch` error row.** Same — include the strategy flag so copying the command works first try.

### Task 5: Fix M5 + M6 — skill polish

**Files:**
- Modify: `skills/vk-execute/SKILL.md`

- [x] **Step 1: M5 — frontmatter description.** `"Execute an agentic phase or task from a plan."` → `"Execute an agentic phase from a plan."`
- [x] **Step 2: M6 — Constraints bullet.** Add `- Migration (if needed) is a separate PR from any phase.` so agents skimming Constraints see the rule.

### Task 6: Regression tests for the guards

**Files:**
- Modify: `tests/integration/test_plan_execute.py`

- [x] **Step 1: `test_format_missing_path_errors`.** Exit 2; "does not exist" in output.
- [x] **Step 2: `test_format_non_plan_file_errors`.** Exit 2; "could not parse" in output.
- [x] **Step 3: `test_non_plan_file_errors_cleanly`.** Parametrised across all four execute sub-commands; asserts exit 2 and "could not parse" surfaces (no traceback).
- [x] **Step 4: Verify full suite.** `uv run pytest -q --no-cov` — 302 passed, 9 skipped.
- [x] **Step 5: Commit.**

## Phase 5: Make CI green [agentic]

Commit `3e4d266` — *style: apply ruff format*.

### Task 1: Unblock CI

**Files:**
- Modify: `src/vk/commands/execute_cmd.py`
- Modify: `src/vk/commands/plan_cmd.py`
- Modify: `tests/integration/test_plan_execute.py`

- [x] **Step 1: Diagnose.** `gh pr checks 21` → lint fails. `gh run view … --log-failed` → `ruff format --check` wants three files reformatted. Tests and typecheck pass.
- [x] **Step 2: Run `uv run ruff format src/ tests/`.** Three files reformatted (whitespace collapsing around tuple/call sites). No behavior change.
- [x] **Step 3: Re-verify.** Full suite still 302 passed; `ruff format --check` clean; `ruff check` clean.
- [x] **Step 4: Commit.**

---

## Self-review checklist

- [x] No flat-as-alternative language in any user-facing surface (skills, CLI help, error messages).
- [x] `_reject_flat` guard called by every `vk execute` sub-command currently registered.
- [x] `TestExecuteRejectsFlat` parametrisation matches the registered sub-command set.
- [x] Migration hints in every error path include a full copy-pasteable `vk plan convert <plan> --to phased --single-phase --yes`.
- [x] Library-level flat support (`parser`, `convert`, `models`, `format`, `config`) preserved — migration still works.
- [x] Regression tests cover missing-path and non-plan-file inputs for both `plan format` and all four execute sub-commands.
- [x] Full suite green: 302 passed, 9 skipped.
- [x] CI green after ruff format pass.
- [ ] Plan status flips to **Complete** when PR #21 merges (manual or via `vk progress sync`).
