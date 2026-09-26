# Journal: 2026-09-26-one-phase-plans

<!-- fr:journal kind=discovery scope=plan id=one-phase-matrix-claim-text created=2026-09-26T11:32:49 phase=1 -->
### one-phase-matrix-claim-text · discovery · set-status cannot edit a row's acceptance text (phase 1)

plan-skeleton-is-not-the-whole-plan's claim was inverted by editing acceptance text in matrix.yaml directly, then set-status for refs/status; refs use #L anchors (::name refs do not resolve).

<!-- fr:journal kind=discovery scope=plan id=fr-plan-skill-line-cap created=2026-09-26T11:32:49 phase=1 -->
### fr-plan-skill-line-cap · discovery · fr-plan SKILL.md is at the 120-line cap (phase 1)

test_under_120_lines binds; the rewritten skeleton bullet had to stay 3 lines.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-09-26T11:32:49 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

a single added assertion with nothing to restructure

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-09-26T11:32:49 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

bookkeeping only (matrix, fragment), nothing to restructure

<!-- fr:journal kind=finding scope=plan id=r1 created=2026-09-26T11:34:12 phase=1 state=open review_scope=in -->
### r1 · finding [open] (reviewer: in scope) · Matrix rows keep the auto-generated placeholder note 'Re-point refs to line anchors.' (phase 1)

Both moved rows should say why they moved (matrix rule: statuses move with a recorded reason).

<!-- fr:journal kind=finding scope=plan id=r2 created=2026-09-26T11:34:12 phase=1 state=open review_scope=out -->
### r2 · finding [open] (reviewer: out of scope) · New matrix row cites no test for the 2+-phases-still-errors half (phase 1)

Existing tests and the goal-phase-one-skeleton-smoke row already pin it; not caused by this change.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-09-26T11:34:12 phase=1 -->
### review-p1 · review · independent review of phase 1: 2 findings, none blocking (phase 1)

Reviewer (feature-dev:code-reviewer, separate context) read gate, tests, skill prose, mirrors, matrix, fragment: no in-scope defect beyond the placeholder notes. Orchestrator additionally ran sync-opencode/sync-hermes --check, bump-version --check and inspected the diff for version surfaces: clean.

<!-- fr:journal kind=finding scope=plan id=r1-resolved created=2026-09-26T11:34:12 phase=1 state=fixed resolves=r1 -->
### r1-resolved · finding [fixed] · resolves r1: Matrix rows keep the auto-generated placeholder note 'Re-point refs to line anchors.' (phase 1)

Notes rewritten with fr acceptance set-status (c81ba771, c488a9ec).

<!-- fr:journal kind=finding scope=plan id=r2-resolved created=2026-09-26T11:34:12 phase=1 state=open resolves=r2 out_of_scope=true -->
### r2-resolved · finding [out-of-scope] · resolves r2: New matrix row cites no test for the 2+-phases-still-errors half (phase 1)

Covered by existing rows and tests; this change did not remove that coverage.
