# Add the optional Refactor step to the fr TDD flow (#340)

## Why

The fr build path (`fr-goal → fr-plan`) says "TDD" but encodes only Red-Green
("test first") and drops Refactor, because `fr-plan/SKILL.md` **paraphrases**
the canonical `superpowers:test-driven-development` skill instead of routing to
it — and the paraphrase lost a third of the cycle. `fr-debugging`, which routes
to the skill, has the full cycle; the build path doesn't. This plan closes that
gap and adds a test guard so the beat can't silently vanish again.

See `docs/superpowers/specs/2026-07-03-tdd-refactor-step-design.md`.

## Approach

TDD, dogfooding the very convention we're adding:

1. **Phase 1 — Guard tests + skill routing.** Write the three enforcement
   tests FIRST (red): they assert `fr-plan/SKILL.md` names `red → green →
   refactor` and routes to `superpowers:test-driven-development`, and that
   `fr-goal/SKILL.md` routes to it too. Then edit the two SKILL.md files to make
   them pass (green): expand fr-plan's `## Rules` TDD bullet + add the plan
   step-shape convention (trailing optional refactor step by default; separate
   `REFACTOR + quality gate` task for larger cleanups; skip when nothing to
   clean), and reword fr-goal's two TDD references to route to the skill
   **net-zero on line count** (it sits at the 120-line hard cap). Task 4 is the
   optional refactor beat itself — reviewed and deliberately **skipped** (prose
   edits, nothing to extract), demonstrating the stay-green/skip loop.

2. **Phase 2 — Version bump + verification.** `scripts/bump-version.py patch`
   (3.5.2 → 3.5.3, required because `plugins/*/skills/**` changed), then ruff +
   full `pytest` green.

## Scope

- **In:** `fr-plan/SKILL.md`, `fr-goal/SKILL.md`, `tests/unit/test_skill_validation.py`,
  version bump.
- **Out (per #340 + Q&A):** `fr-execute/SKILL.md` — silent on TDD but delegates
  to `superpowers:executing-plans`, which carries the cycle; no `fr` CLI code
  change (docs + guard tests only).

## Manual work

None. Fully agent-completable — no `[manual]` phase.
