# Journal: 2026-09-20-fr-run-cursor-cluster

<!-- fr:journal kind=discovery scope=plan id=nrb-P1-T3 created=2026-09-20T15:29:53 -->
### nrb-P1-T3 · discovery · no-refactor-because P1.T3

This task runs lint, types and the full suite, then flips one acceptance row with fr acceptance set-status. It writes no product code — there is nothing to restructure, and inventing a refactor step here would be ceremony that dilutes the marker's meaning where it is real (P1.T1.S3, P1.T2.S3 both do genuine extraction).

<!-- fr:journal kind=discovery scope=plan id=nrb-P3-T3 created=2026-09-20T15:29:53 -->
### nrb-P3-T3 · discovery · no-refactor-because P3.T3

This task edits two sentences of SKILL.md prose, regenerates the OpenCode mirror with scripts/sync-opencode.py, and runs the gates. The mirror is GENERATED — refactoring it is forbidden by AGENTS.md, and two sentences of token-budgeted prose have no internal structure to improve.

<!-- fr:journal kind=discovery scope=plan id=nrb-P4-T3 created=2026-09-20T15:29:53 -->
### nrb-P4-T3 · discovery · no-refactor-because P4.T3

This task runs fr plan self-review over the live plan corpus and the full suite, fixing any inline-constructed test plan that violates the new rule. Those fixes are corrections to test DATA, not code with a shape; the rule's own extraction happened in P4.T1.S3 (_trailing_manual_block) and P4.T2.S3 (merging the two passes).

<!-- fr:journal kind=discovery scope=plan id=nrb-P5-T3 created=2026-09-20T15:29:54 -->
### nrb-P5-T3 · discovery · no-refactor-because P5.T3

This task runs the gate sweep and flips one acceptance row. The refactor for this phase's real code is P5.T2.S3, which re-reads _advance_group end to end after it has accumulated the running-check, the manual filter and the preflight.

<!-- fr:journal kind=discovery scope=plan id=nrb-P6-T1 created=2026-09-20T15:29:54 -->
### nrb-P6-T1 · discovery · no-refactor-because P6.T1

This task verifies the external renderer, edits three passages of published prose, and regenerates the HTML. The .html is generated and must never be hand-edited (explainers-currency.md); the .md is narrative prose for a reader who has never seen this repo. Neither has code structure to improve. The plan's whole-diff refactor pass is P6.T2.S3.
