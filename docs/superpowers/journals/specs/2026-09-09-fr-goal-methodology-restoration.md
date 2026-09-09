# Journal: 2026-09-09-fr-goal-methodology-restoration

<!-- fr:journal kind=review scope=spec id=spec-review-464 created=2026-09-09T08:41:13 -->
### spec-review-464 · review · spec-review: all named modules verified on disk

Verified all §5 implementation targets exist: fr/workflow/{model,check,resolve,shapes}.py, fr/run/{model}, fr/commands/{run_cmd,journal_cmd,plan_cmd}.py, fr/journal/{model}, fr/plan_ops.py, workflows/fr-goal.yaml, skills fr-goal/fr-plan/fr-execute, agent fr-phase-executor.md. No findings; spec is implementable as written.

<!-- fr:journal kind=decision scope=spec id=skeleton-override-2026-09-09-fr-goal-methodology-restoration created=2026-09-09T09:31:40 -->
### skeleton-override-2026-09-09-fr-goal-methodology-restoration · decision · No walking skeleton: framework-internals change

This plan modifies fr's own engine (workflow shapes, run cursor, self-review gates) and is verified by the repo's existing CI suite plus new unit tests. There is no deployable surface and no external system to capture; marking phase 1 a skeleton would be dishonest. Override logged per the skeleton gate's override path.
