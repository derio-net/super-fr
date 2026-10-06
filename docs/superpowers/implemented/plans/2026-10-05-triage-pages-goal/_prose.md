# Triage pages: one goal per page, one home per fact

Spec: `docs/superpowers/specs/2026-10-05-triage-pages-goal-design.md` (issues #970, #968, #887).

Five phases, one per independently reviewable ask:

1. **Page partition** (skeleton): the shared page chrome and fragment module, then each page cut to
   its goal: architecture slimmed, origins reordered, and the new history page with its verb. The
   finished-wave predicate lands here because the board and the history page split on it.
2. **Board first screen**: transitions table, Tier column, collapsed sections, stage-filtered batch
   cards. This phase carries the visual evidence.
3. **Data**: origins.yaml schema 2, and severity and duplicates on judgements, shown on the pages.
4. **State export**: the `fr triage state` verbs, and the driver's per-wave export PR with its crash
   window. Tier hard: it changes the driver's decision table and adds a forge write path.
5. **Docs and this repo's state**: skills plus both mirrors, then this repo's `docs/triage/`. That
   needs #969 merged first, and the phase stops blocked otherwise.

Phase 4 depends only on phase 1 (`finished_waves`), so it can follow phase 1 directly if phases 2
and 3 stall.
