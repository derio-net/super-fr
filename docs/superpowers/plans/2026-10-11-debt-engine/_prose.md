# One debt engine — implementation plan

Spec: `docs/superpowers/specs/2026-10-11-debt-engine-design.md` (super-fr#1121).

Five agentic phases, one per independently reviewable ask:

1. **The `skipped` split** (skeleton, hard): the status vocabulary every other phase counts
   with, plus the matrix 4→5 and record 8→9 migrations. It lands first because it is the
   riskiest change, a shared gate and a migration chain, and because the engine's definition
   of debt depends on it.
2. **The engine** (`fr debt`, read-only): the report every surface renders.
3. **Owed actions** (hard): the journal kind 1→2, Test Plan outcomes, the archive hold on
   every mode, owed filing and discharge. It feeds the engine's Owed section.
4. **Weekly issue, archive PR, forge adapters and CI scaffolds.** These need the engine and
   the archive hold.
5. **Triage sets and the Debt panel.** This phase reads the figures encoding from phase 2.

Every phase whose work moves a stamp runs `uv run fr migrate artifacts --yes` in the
worktree and commits the result. The weekly rename and the archive PR are post-merge `live`
rows (the spec's Test Plan). There is no `[manual]` phase.
