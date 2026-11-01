# CI and release speed — plan

Spec: `docs/superpowers/specs/2026-11-01-ci-speed-design.md`.

Three asks, three agentic phases, in risk order:

1. **Fast matrix parsing** (R1–R3): the root cause of the 418 s long-tail
   test, and a product speed-up for every consumer repo. It is small and goes
   first as the skeleton: it proves the branch's CI loop (`tests: ci`, because
   no full suite may run on the operator's Mac) before the CI layout changes.
2. **CI** (R4–R7, R12 for ci.yml, R13, R14): CI-derived shard weights through
   one plan artifact, the `split-check` completeness gate, 6 shards, coverage
   on 3.14, timeouts, the watcher's GET fix and the new budgets. It ends by
   refreshing the committed `.test_durations` from its own CI run.
3. **Release** (R8–R12): `release.yml` becomes prepare → collect + 6 test
   shards → split-check → publish, and `release.py` gains subcommands. A moved
   `main` now stops as superseded instead of re-testing. It is `hard`: every
   release relies on this path, and it changes a gate's mechanics.

Verification: each phase runs only targeted tests locally, through
`~/.cache/fr/coord/testslot.sh`, and lets the draft PR's CI run the full suite
(`tests: ci`). The release phase can only be walked post-merge (Test Plan 1–2).

Not touched: `tests/conftest.py` and `fr/artifacts/*`, which parallel goal
runs are editing.
