# Exit gates — implementation plan

Spec: `docs/superpowers/specs/2026-10-14-exit-gates-design.md`
(super-fr#1189, #1155, #667; one PR on `feat/batch-exit-gates`).

## Shape

Eight agentic phases, one per independently reviewable ask, run serially in the
order every later one builds on:

1. **Exit model** (skeleton). Gate vocabulary, manifest schema 2, spec `gate:`
   lines, the `.fr/triage.yaml` remap, `run_exit`, and `fr verification exit`,
   plus #1155's `row_verification_issues`. Everything after reads the exit this
   phase computes.
2. **Labels and `fr verification set`.** PR-level adapter methods, label sync at
   the resolves, and the downgrade guard.
3. **`deliver` leftovers.** Journal decision tokens, the `record` kind 9 → 10
   migration, `fr journal file`, `unaccounted`, and the widened Closes guard.
4. **Driver routing.** Facts read merged-PR labels and the run cursor. Gated
   batches skip close-out. The awaiting-live and gate-pass actions, and
   `fr gate pass`.
5. **Board lanes.** The four Needs-you lanes, from the cursor and the gate
   labels, and the single `conflicting` predicate.
6. **Collected close-out.** `fr triage batch closeout`, one per repo,
   attribution by `event.archive`, and the one close-out hand-back.
7. **Release gating.** `fr release status`, RC versions across the tooling, RC
   or final in `release.py`, and floors that admit RCs.
8. **Install channels.** `bootstrap.sh --version`, and `install.sh` accepting a
   tagged checkout.

## Cross-cutting rules for every phase

- **TDD.** Each task goes red, then green, then refactor (or records why there
  is no refactor). Run targeted tests in the phase; run the full suite only
  through the repo's test slot.
- **Mirrors.** After a skill edit, run BOTH `scripts/sync-opencode.py` and
  `scripts/sync-hermes.py`. fr-* SKILL.md files are capped at 120 lines.
- **Schema numbers.** `FACTS_SCHEMA` (phase 4) and the judgements schema
  (phase 6) move to main's number plus one. Re-check against `origin/main`
  before pushing: parallel PRs collide on these.
- **Record kind (phase 3).** Its stamp moves, which brings a migration, a
  validator, and `fr migrate artifacts --yes`, all committed in the same phase.
- **Matrix.** Move rows with `fr acceptance set-status`, never by hand. The four
  `live` rows stay walk-owed after merge; their phases only add unit and
  integration levels.
- **Issue refs.** No phase names a member issue as `tracking_issue`.
