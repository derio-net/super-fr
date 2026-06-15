# fr-debugging — `superpowers:systematic-debugging`, wrapped in isolation

**Date:** 2026-06-15
**Status:** Approved design (batched Q&A answered) — one-shot with `/fr-goal`.
**Target repo:** derio-net/super-fr (plugin: `super-fr`)

## Problem

The fr system wraps two superpowers process skills so they run inside the
isolation layer instead of touching the base repo: `fr-brainstorming` wraps
`superpowers:brainstorming`, and `fr-goal` sequences brainstorming → plan →
implement to a PR. **Debugging has no fr-native wrapper.** When a bug surfaces
— in a feature being built under fr-goal, or as a standalone report — the
operator either runs plain `superpowers:systematic-debugging` against the base
working tree (violating the "base repo is never touched" invariant the rest of
the fr pipeline enforces), or hand-rolls isolation each time.

`systematic-debugging` is the right *method* (Iron Law: no fixes without root
cause; four phases; the 3+-fixes architecture gate). What's missing is the
*placement*: run it in a worktree + devcontainer, land the failing test + the
root-cause fix on a branch, and deliver a reviewed PR — the same goal-to-PR
ergonomics fr-goal gives features.

## Requirement

Add a new skill `fr-debugging` (`plugins/super-fr/skills/fr-debugging/SKILL.md`)
that wraps `superpowers:systematic-debugging` the way `fr-brainstorming` wraps
brainstorming: **the skill owns WHERE debugging happens (isolation) and the
autonomy contract; it delegates HOW (the four phases, the Iron Law, the craft)
to the wrapped skill, unchanged.**

It runs autonomously to a reviewed PR — like fr-goal, no intermediate approval
gates — with two faithfully-preserved hard stops where systematic-debugging
genuinely requires the human.

### Autonomy model (Q1: autonomous + hard stops)

The skill runs the four phases through to a PR without pausing, EXCEPT at the
two checkpoints that are genuinely operator-owned. At those it stops, states
what it found / tried, and asks — a wrong guess shipped in a PR costs more than
a paused run (the same blocked-→-ask contract fr-goal already states):

1. **"I don't understand X" (Phase 3, step 4).** When investigation cannot
   form a confident single hypothesis — the bug is non-reproducible, or the
   evidence is genuinely ambiguous — pause and ask rather than guess.
2. **3+ fixes failed → question the architecture (Phase 4, step 5).** This is
   explicitly *not* a failed hypothesis but a wrong-architecture signal that
   `systematic-debugging` reserves for the human partner. After the 3rd failed
   fix, the skill stops, presents the pattern (each fix revealing a new
   coupling/symptom), and asks before any 4th attempt.

Everything else — reading errors, reproduction, evidence instrumentation,
pattern analysis, single-hypothesis testing, the TDD failing-test-then-fix of
Phase 4, the milestone review, and PR creation — runs autonomously.

The fully-autonomous "architecture concern becomes a PR note instead of a
pause" variant was rejected: shipping a guess when the bug is architectural is
exactly the failure mode the gate exists to prevent.

### Isolation entry (Q2: reuse-if-present, else fresh)

Unlike fr-brainstorming/fr-goal (which always bring up a fresh feature
workspace), debugging is frequently triggered *inside* existing work:

- **Already inside an fr isolation workspace** (e.g. a bug found mid-fr-goal
  implementation): **reuse it.** The failing test + fix land on that feature's
  branch and ride its existing PR — a bug found while building a feature must
  not spawn a competing PR. Detect via `fr isolation status` (an active
  workspace for the current branch).
- **Cold start** (standalone bug report, no active workspace): bring up a
  fresh workspace on a `fix/<slug>` branch —
  `fr isolation up --branch fix/<slug> [--profile <name>]` — exactly the
  fr-brainstorming hard gate. **No devcontainer profile → HARD STOP**, offer
  the fr-init interview (under fr-goal, treat as a blocker: pause, fr-init,
  resume).

Either way, from the first command on, all work goes through the exec-bridge
(`fr isolation exec -- …`); reads/edits operate on the worktree.

### Investigation log (Q3: durable debugging log)

The root-cause investigation is recorded as a **durable, committed log** at
`docs/superpowers/debugging/<YYYY-MM-DD-slug>.md`, written in the worktree and
committed alongside the fix. It is the debugging analogue of a spec — a
permanent, searchable record — but lighter: a bug fix does NOT enter the
spec → plan pipeline. The log captures, per the four phases:

- **Symptom & reproduction** — the exact failing behavior and repro steps.
- **Evidence** — error messages, the data-flow trace, the component-boundary
  instrumentation output that localized the failure.
- **Root cause** — the single confirmed cause, stated as "X because Y".
- **Fix** — the one change at the source, and the failing-test-first that
  pins it.
- **Rejected hypotheses** — what was tested and ruled out (so the next person
  doesn't re-walk dead ends).

The PR body summarizes this log and links it.

### Trigger wiring (Q4: auto-supersede in fr repos)

Add a **Debugging Override** to `plugins/super-fr/rules/fr-plan-override.md`,
mirroring the existing Brainstorming Override:

> In a repo with fr plans (`docs/superpowers/plans/`) or devcontainer profiles
> (`.devcontainer/<profile>/`), debugging a bug / test failure / unexpected
> behavior uses `fr-debugging` instead of plain
> `superpowers:systematic-debugging` — it enters isolation first, so the base
> repo is never touched. Plain systematic-debugging remains for non-fr repos.

Per the project's CLAUDE.md "Bridge audit rule" convention, the user-level
mirror of this rule lives at `~/.claude/rules/fr-plan-override.md` (operator
-owned, outside the repo). This PR **must flag the operator-side update in its
description** so the two stay in sync — the repo change alone does not move the
user-level file.

## Skill scope (mirror fr-brainstorming)

- The skill owns WHERE debugging happens (isolation), the autonomy contract,
  the two hard stops, and the durable-log artifact.
- It does NOT restate the four-phase method, the Iron Law, the red flags, or
  the supporting techniques (`root-cause-tracing.md`, `defense-in-depth.md`,
  `condition-based-waiting.md`) — those are delegated to
  `superpowers:systematic-debugging`, invoked unchanged. Restating them would
  duplicate a skill that evolves independently.
- Phase 4's failing test uses `superpowers:test-driven-development` (as
  systematic-debugging already directs); verification before the PR uses
  `superpowers:verification-before-completion`; the milestone review uses
  `superpowers:requesting-code-review` / `receiving-code-review` — same
  building blocks fr-goal composes.

## Files to change

1. **`plugins/super-fr/skills/fr-debugging/SKILL.md`** — new skill (the
   deliverable). Frontmatter `name: fr-debugging` + a `description` whose
   trigger phrasing covers "debug", "bug", "test failure", "unexpected
   behavior", "root cause" inside an fr repo.
2. **`packages/fr/src/fr/commands/skills_cmd.py`** — add an `fr-debugging`
   tuple to `SKILLS` (REQUIRED: `test_skill_files_match_skills_list` asserts
   `on_disk == listed`; a new skill dir without the entry fails CI).
3. **`plugins/super-fr/rules/fr-plan-override.md`** — add the Debugging
   Override section.
4. **`README.md`** — add an `fr-debugging` row to the skills table (line ~208
   neighborhood) and bump the "7 skills" count on line 20; optionally note it
   in the flow diagram prose.
5. **Version bump** — new skill ⇒ **minor** per CLAUDE.md versioning scheme:
   `3.1.8 → 3.2.0` via `scripts/bump-version.py minor` (updates the three
   sources + `uv.lock`; `bump-version.py --check` runs in CI).

## Testing & verification

- **Drift guard (the real test surface).** `test_skills_cmd.py` already
  enforces the SKILLS↔dirs bijection; adding the skill + the SKILLS tuple makes
  `test_skill_files_match_skills_list` and `test_skills_list_matches_skill_files`
  pass. Confirm `uv run pytest tests/unit/test_skills_cmd.py -q` green, and the
  `fr skills` subprocess smoke test still exits 0 with the new row present.
- **No new Python runtime behavior** — fr-debugging is a process skill, not a
  CLI subcommand (like fr-goal/fr-brainstorming, it adds no `fr` verb). So the
  testable change is the SKILLS list + docs; there is no module to unit-test
  beyond the drift guard.
- **Full gate before PR** (per CLAUDE.md / ci.yml): `uv run ruff format
  packages/ tests/`, `ruff check`, `mypy packages/fr/src …`, `uv run pytest -q
  --no-cov`, and `bump-version.py --check`.
- **Self-consistency check:** the SKILL.md must not duplicate
  systematic-debugging's phase content (scope-creep smell); a reviewer reads it
  against fr-brainstorming for parity of shape.

## Non-goals

- **No new `fr` CLI subcommand.** fr-debugging orchestrates existing verbs
  (`fr isolation {status,up,exec,down}`); it is a skill, not a command.
- **No change to `systematic-debugging` itself.** It is wrapped, not forked or
  edited.
- **No spec/plan pipeline for bug fixes.** The durable debugging log replaces
  spec+plan for this lighter-weight flow.
- **No auto-merge.** Like fr-goal, the operator merges the PR.
- **fr-goal does not call fr-debugging automatically** in this iteration — when
  a bug arises mid-fr-goal implementation, the operator (or the implementing
  context) invokes fr-debugging, which reuses the live workspace. A future
  iteration may wire fr-goal's implement step to delegate explicitly.

## References

- Wrapped skill: `superpowers:systematic-debugging` (Iron Law, four phases,
  supporting techniques `root-cause-tracing.md` / `defense-in-depth.md` /
  `condition-based-waiting.md`).
- Closest precedent: `plugins/super-fr/skills/fr-brainstorming/SKILL.md`
  (wrap-one-superpowers-skill-in-isolation; "owns WHERE not HOW").
- Autonomy contract precedent: `plugins/super-fr/skills/fr-goal/SKILL.md`
  (no-gates + when-blocked-stop-and-ask).
- Isolation mechanics: `plugins/super-fr/skills/fr-isolation/SKILL.md`,
  `packages/fr/src/fr/isolation/`.
- Drift guard: `tests/unit/test_skills_cmd.py`; skills overview source
  `packages/fr/src/fr/commands/skills_cmd.py`.
- Override rule: `plugins/super-fr/rules/fr-plan-override.md` (+ user-level
  mirror `~/.claude/rules/fr-plan-override.md`).
- Versioning / bump policy: `CLAUDE.md` (Release / version bumping).
