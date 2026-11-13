<!-- fr:journal-schema=4 -->
# Journal: 2026-11-13-writing-standards-docs

<!-- fr:journal kind=decision scope=plan id=plan-gate-last created=2026-11-13T21:49:14+00:00 -->
### plan-gate-last · decision · The CI gate turns on in the last phase

ci-ok depends on site-build (.fr/ci.yaml gate_checks: [ci-ok]); turning the writing-standard step on before every page passes would make every phase's tests: ci evidence red.

<!-- fr:journal kind=decision scope=plan id=plan-fact-keeper-in-review created=2026-11-13T21:49:14+00:00 -->
### plan-fact-keeper-in-review · decision · Fact-keeper reviews run in each phase's review step

A phase executor cannot dispatch agents; the executor writes each page's baseline outside the repo and the orchestrator dispatches one fact-keeper per page during review-phase, recording the results in that record (R8).
