# fr-debugging — systematic-debugging wrapped in isolation

## Goal

Add an fr-native debugging skill that runs `superpowers:systematic-debugging`
inside the isolation layer and delivers a reviewed PR — the debugging analogue
of how `fr-brainstorming` wraps brainstorming and `fr-goal` wraps the
feature pipeline. The skill owns WHERE debugging happens (isolation) and the
autonomy contract; it delegates HOW (the four phases, the Iron Law, the
supporting techniques) to the wrapped skill, unchanged.

See `docs/superpowers/specs/2026-06-15-fr-debugging-design.md` for the approved
design and the four batched-Q&A decisions:

- **Autonomous + hard stops** — runs to a PR with no approval gates, EXCEPT
  the two genuinely operator-owned checkpoints (Phase 3 "I don't understand X"
  and Phase 4 "3+ fixes → question the architecture"), which pause and ask.
- **Reuse-if-present, else fresh** — reuse an active fr isolation workspace
  when invoked inside one (fix rides the feature's branch/PR); else bring up a
  fresh `fix/<slug>` workspace.
- **Durable debugging log** at `docs/superpowers/debugging/<date-slug>.md`,
  committed with the fix.
- **Auto-supersede in fr repos** via a Debugging Override added to
  `fr-plan-override.md` (repo-local), with the user-level mirror flagged for
  the operator.

## Approach

The change is documentation + thin wiring, not new runtime logic. fr-debugging
adds NO `fr` CLI subcommand — it orchestrates existing verbs
(`fr isolation {status,up,exec,down}`). The only automated test surface is the
existing SKILLS↔dirs **drift guard** in `tests/unit/test_skills_cmd.py`, which
we exploit as the failing-first test: dropping the new `SKILL.md` makes it RED,
adding the matching `SKILLS` tuple makes it GREEN.

## Phases

1. **Skill + drift-guard wiring (TDD).** Author `SKILL.md`; confirm the drift
   guard goes red; add the `SKILLS` tuple; confirm green.
2. **Trigger override + README.** Add the Debugging Override to the repo-local
   rule; add the README skills row and bump the count; confirm `fr skills`
   prints the new row.
3. **Version bump + full gate.** Minor bump (3.1.8 → 3.2.0); run the full
   ci.yml-parity gate (ruff, mypy, pytest, bump-version --check).
4. **[manual] User-level rule mirror.** Back-loaded operator step: copy the
   Debugging Override into `~/.claude/rules/fr-plan-override.md`. Ships
   unimplemented, flagged in the PR body.

## Non-goals

- No new `fr` CLI subcommand. No edits to `systematic-debugging` itself. No
  spec/plan pipeline for bug fixes (the durable log replaces it). No
  auto-merge. fr-goal does not yet auto-delegate to fr-debugging.
