# CI economy (spec 2026-11-24-ci-economy)

Four phases, one per ask group of derio-net/super-fr#1647:

1. **One cancelled-check rule** (R3, R4): `fr/checkstate.py` and every reader that turns a check into a verdict; a cancelled combination check becomes a Need. Skeleton: its smoke adds the module and the change fragment.
2. **ci.yml lanes** (R1, R2, R5-R7, R15-R18): `scripts/ci_lane.py` (`classify`, `landed`, `verdict`) and the workflow's concurrency, `classify` job, lane conditions, `scoped-tests` and lane-aware `ci-ok`. Tier hard: it changes the one required check of `main`.
3. **own_artifacts** (R19, R20): the marker, the tripwire that keeps it on every root-reading test module, and `--fr-scope`'s selection.
4. **Generated files and stamps in the queue** (R8-R14): `fr/triage/regen.py`, the builder's plumbing, `.fr/triage.yaml`'s `mirrors:`/`generated:`, facts schema 17.

Phases 2-4 depend only on phase 1 (shared fragment and module). Each phase runs the repo's fast tier last (`.fr/ci.yaml` `tests: ci`); CI on the PR is the suite evidence.
