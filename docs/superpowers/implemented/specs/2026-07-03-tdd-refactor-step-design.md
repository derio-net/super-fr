# Spec: Add the optional Refactor step to the fr TDD flow

**Date:** 2026-07-03
**Issue:** #340
**Status:** design
**Target repo:** derio-net/super-fr

## Problem

The fr planning/execution layer says "TDD" but encodes only the **Red-Green**
half ("test first") and never the **Refactor** step, even though the canonical
`superpowers:test-driven-development` skill it builds on defines the full
**Red-Green-Refactor** cycle.

The root cause is a **paraphrase leak**: `fr-plan/SKILL.md` restates TDD in its
own words ("TDD: test first, always") instead of routing to the canonical
skill, and the restatement silently drops a third of the cycle. `fr-goal`
inherits the same gap by saying "TDD-shaped steps" / "TDD per step" without
pointing at the skill. `fr-debugging`, which *does* route to
`superpowers:test-driven-development`, gets the complete cycle — so the build
path (fr-goal → fr-plan) and the debug path are internally inconsistent.

This is "not standardized," not "never done": some plan authors add a refactor
task by hand (the plan format already accommodates it), but whether a plan gets
a refactor beat depends on the author remembering, not on the TDD rule.

## Goal

Make an **optional Refactor step** a standard part of the fr TDD flow —
surfaced whenever it's warranted (duplication/naming/extraction to clean while
staying green) and skipped when it isn't. Prefer **routing to the canonical
skill** over re-paraphrasing it, and **enforce** the invariant with tests so
the beat cannot silently disappear again (this repo's "enforce, don't prose"
convention, #328).

## Non-goals

- Not mandating a refactor step on every task — it stays optional/conditional,
  matching the skill's "after green *only*" stay-green-or-skip loop.
- Not touching `fr-execute/SKILL.md`. It is silent on TDD but delegates
  implementation to `superpowers:executing-plans`, which carries the cycle;
  the issue explicitly scopes to fr-plan + fr-goal + the plan convention.
- No behavioral code change to the `fr` CLI — this is a skills-doc change plus
  guard tests.

## Design

### 1. `fr-plan/SKILL.md` `## Rules` — expand the TDD rule (primary fix)

Replace the current bullet (line 65):

> - TDD: test first, always. No speculative generality.

with a rule that names all three beats **and** routes to the canonical skill.
It must contain the canonical token `red → green → refactor` (the enforcement
test asserts this exact substring) and the string
`superpowers:test-driven-development`:

> - TDD (`superpowers:test-driven-development`): **red → green → refactor**.
>   Test first (red → green), then an **optional** refactor step per task when
>   there's duplication / naming / extraction to clean — stay green, add no
>   behavior; **skip it when there's nothing to clean**. No speculative
>   generality.

### 2. `fr-plan/SKILL.md` — plan step-shape convention

Add a short convention (a bullet under Rules, or a compact note) standardizing
how the optional refactor step appears in a plan. Document **both** forms the
existing plans already use, defaulting to the trailing step:

- **Default — trailing optional step:** after a task's red→green steps
  (`P<n>.T<n>.S1` test, `S2` implement), add an **optional** trailing refactor
  step (`P<n>.T<n>.S3`) for small cleanups.
- **Larger cleanups — a separate `REFACTOR + quality gate` task** (the form a
  few shipped plans already use, e.g.
  `docs/superpowers/implemented/plans/2026-06-16-readme-ux-and-plan-config-cleanup`).
- **Skip entirely when there's nothing to clean** — trivial tasks carry no
  empty refactor step (matches the skill's stay-green/skip loop).

### 3. `fr-goal/SKILL.md` — route to the canonical skill

`fr-goal/SKILL.md` is at the **120-line hard cap** (enforced by
`test_under_120_lines`), so edits must be **net-zero on line count** — change
wording in place, add no new lines.

- Step 4 (line ~64): change "TDD-shaped steps" so it routes to the cycle, e.g.
  "TDD-shaped steps (red → green → refactor per
  `superpowers:test-driven-development`)".
- Step 6 (line ~88): change "TDD per step" similarly, e.g. "full red→green→
  refactor per `superpowers:test-driven-development`".

At least one occurrence must contain the literal
`superpowers:test-driven-development` (the enforcement test asserts it). Both
edits stay on their existing lines — no line added or removed.

### 4. Enforcement — guard tests (this issue's durable fix)

Add per-skill content assertions to
`tests/unit/test_skill_validation.py`, following the existing
`test_fr_execute_*` skip pattern (parametrized over `_SKILL_DIRS`, `skip`
unless the target skill):

- `test_fr_plan_tdd_names_all_three_beats` — for `fr-plan`, assert the
  SKILL.md text contains the canonical token `red → green → refactor`
  (case-insensitive).
- `test_fr_plan_routes_to_canonical_tdd_skill` — for `fr-plan`, assert the text
  contains `superpowers:test-driven-development`.
- `test_fr_goal_routes_to_canonical_tdd_skill` — for `fr-goal`, assert the text
  contains `superpowers:test-driven-development`.

These fail today (red) and pass after the doc edits (green), and they trip if a
future paraphrase ever drops the beat or the routing — exactly the drift that
produced #340.

### 5. Version bump

Touches `plugins/*/skills/**` and `tests/**` (the tests alone wouldn't require
it, but the skill edits do), so bump per `CLAUDE.md`'s release policy:
`scripts/bump-version.py patch` → `3.5.2` → `3.5.3`. The helper rewrites every
version source (root + 4 package `pyproject.toml`, both `plugin.json`, and both
`marketplace.json` entries) and refreshes `uv.lock`; commit all of them
together. `scripts/bump-version.py --check` is the source of truth that they
agree.

## Affected files

| File | Change |
|---|---|
| `plugins/super-fr/skills/fr-plan/SKILL.md` | Expand TDD rule (§1) + step-shape convention (§2) |
| `plugins/super-fr/skills/fr-goal/SKILL.md` | Route to canonical skill, net-zero lines (§3) |
| `tests/unit/test_skill_validation.py` | Three guard tests (§4) |
| version sources (root + 4 pkg `pyproject.toml`, 2 `plugin.json`, `marketplace.json`) + `uv.lock` | Version bump 3.5.2 → 3.5.3 (§5) |

## Verification

- `uv run pytest tests/unit/test_skill_validation.py -q` — the three new tests
  pass (and fail before the SKILL.md edits, proving red first).
- `uv run pytest -q --no-cov` — full suite green (including
  `test_under_120_lines` still passing for fr-goal).
- `scripts/bump-version.py --check` — three version sources agree.
- `uv run ruff format packages/ tests/` and `ruff check` clean.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|-------------|------|--------|
| 2026-07-03-tdd-refactor-step | `derio-net/super-fr` | `2026-07-03-tdd-refactor-step` | — |
