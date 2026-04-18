# Deprecate Flat Plans — Design

## Problem

The `vk` toolchain shipped with two plan shapes: **flat** (`### Task 1` → `- [ ] Step 1`) and **phased** (`## Phase 1` → `### Task 1` → `- [ ] Step 1`). Two distinct problems grew out of that design:

1. **Review-grain conflation.** The `vk-execute` skill documented the rule "one phase/task = one PR." Applied to flat plans, it meant "one task = one PR." On a real 24-task flat plan (kid-laptops plan 6: Hermes Agent), the first task was a 4-file role skeleton — a PR with ~zero review value on its own. The natural review grain was the enclosing subsystem (agent-daemon, agent-speech, agent-client, agent-onboarding) — phases in everything but name.

2. **Shape-as-routing signal.** Operators used flat plans to mean "execute locally; don't dispatch to GitHub Issues." But dispatch intent already lives in `plan-config.yaml`'s `dispatch:` block. Plan shape was carrying a second, orthogonal meaning, and the two kept getting tangled in skill logic — e.g. `vk plan format` derived the expected shape from dispatch config, and `vk plan new` branched on that to produce flat vs phased skeletons.

The right model: **plan shape reflects review units; routing lives in `plan-config.yaml`**. These are orthogonal concerns. Flat plans were trying to express both at once.

## Options considered

1. **Keep flat; tighten the rule.** Change "one phase/task = one PR" to "one flat-plan = one PR" and "one phase = one PR." Keeps flat as a valid shape; plan granularity is picked at authoring time. **Rejected.** Still carries the dual-meaning. Encourages flat-as-dispatch-opt-out. And a plan large enough to warrant phases shouldn't be expressible as a single-PR flat plan anyway — if it's big enough to need structure, it should have phases.

2. **Deprecate flat; auto-migrate on encounter.** All plans are phased. Legacy flat plans are legacy artifacts — when the skill or CLI encounters one, migrate it (the `vk plan convert` CLI already exists with `--single-phase`, `--group-by-tag`, `--one-per-task` strategies). No alternative path that executes a flat plan directly. **Accepted.** See below.

3. **Retire flat entirely; rip out parser/model support.** Break legacy plans on load; force a hard one-time migration pass. **Rejected for this PR.** Too aggressive given at least one production plan (kid-laptops plan 6) was flat at the time of writing. Left as a follow-up once all known plans are migrated.

## Decision

Adopt option 2:

- **Skills.** `vk-execute`, `vk-plan`, `vk-dispatch` SKILL.md files present phased as the only supported shape. `vk-execute` gains a Procedure step 0: run `vk plan format <plan>`; if `flat`, run the Migration section (documented with two flows — automatic+review or guided) and commit as its own PR **before** any phase execution.
- **CLI enforcement.** Every `vk execute` sub-command and `vk dispatch` entry point calls a `_reject_flat` guard. Flat input exits 2 with a copyable `vk plan convert` command. `vk plan new` always emits phased. `vk plan convert --to flat` is no longer accepted (only `--to phased`). `vk plan format` accepts either a plan file (actual shape) or a repo root (legacy config-derived behavior).
- **Library internals stay bilingual.** `vk.plan.{parser, convert, models, format, config}` still understand flat input — that's the machinery migration uses to read legacy plans. Removing this layer is a deliberate non-goal for the current PR.

The two migration flows:

**Automatic + review** (default):

```bash
vk plan convert <plan> --to phased --single-phase --dry-run   # preview
vk plan convert <plan> --to phased --single-phase --yes        # apply
git add <plan> && git commit -m "plan: migrate to phased"
```

**Guided** (when the plan has natural subsystem boundaries — multiple roles / services / modules):

1. Wrap all tasks in Phase 1 via `--single-phase`.
2. Show the operator the task list; ask where phase boundaries should go.
3. Edit the plan: replace the single `## Phase 1:` with N phase headers at the chosen boundaries; renumber tasks per phase (Task 1 of each phase starts at 1).
4. `vk plan self-review` to confirm shape.
5. Commit as its own PR.

## Blast radius

- **New plans:** only phased. No migration needed.
- **In-flight flat plans:** one migration PR per plan. The converter preserves previously-ticked checkboxes and renumbers step IDs to `P<n>.T<n>.S<n>`.
- **Library consumers:** `to_flat` remains in `vk.plan.convert` (library-level tests still cover it); no CLI exposure. `PlanFormat.FLAT` enum member stays. `ProfileConfig.format` still returns `FLAT` when dispatch is disabled, consumed only by `vk plan format` in directory mode.

## Validation in practice

kid-laptops plan 6 (Hermes Agent) — 24 flat tasks → 5 phases via `vk plan convert --to phased` + hand-edit to split at role boundaries. Produces 5 review PRs instead of 24. See [derio-net/kid-laptops#3](https://github.com/derio-net/kid-laptops/pull/3).

## Follow-ups (not in this PR)

1. Fold flat parsing out of `vk.plan.parser`; drop `PlanFormat.FLAT`. Requires all known plans migrated first.
2. Retire `to_flat` and its unit tests.
3. Collapse `ProfileConfig.format = FLAT` branch — consumed only by `vk plan format` directory mode, itself marked legacy.
4. Refactor `_reject_flat` to return `(plan, text)` and eliminate the double-parse in `check-deps` and `pr-body`.
5. Bind `TestExecuteRejectsFlat` parametrisation to `execute_app.registered_commands` so new sub-commands automatically inherit the flat-rejection smoke test.

## Implementation Plans

| Plan | Repo | File | Status | Depends on |
|------|------|------|--------|------------|
| Deprecate Flat Plans Implementation Plan |  | `docs/superpowers/archived-plans/2026-04-18-deprecate-flat-plans.md` | Complete | — |
