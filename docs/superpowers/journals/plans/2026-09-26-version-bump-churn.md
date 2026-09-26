# Journal: 2026-09-26-version-bump-churn

<!-- fr:journal kind=decision scope=plan id=plan-phase-shape created=2026-09-26T08:15:24 -->
### plan-phase-shape · decision · Six phases - skeleton surface list, PR gate, release workflow, acceptance, docs/config, manual live release

Acceptance (P4) depends only on the skeleton so it is independent of the release machinery.
The live first release is back-loaded as a [manual] phase; the PR ships it unimplemented.
Invariant for every phase: no version value changes (spec §4) - this PR's own gate proves rule 2.
