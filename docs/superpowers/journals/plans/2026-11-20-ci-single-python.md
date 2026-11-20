<!-- fr:journal-schema=4 -->
# Journal: 2026-11-20-ci-single-python

<!-- fr:journal kind=discovery scope=plan id=ruff-unsafe-fix-partial-rename created=2026-11-20T08:29:30+00:00 phase=1 -->
### ruff-unsafe-fix-partial-rename · discovery · ruff --unsafe-fixes for UP047 renames type params inconsistently on its first pass (phase 1)

The first `--fix --unsafe-fixes` pass wrote `def _poll[T](check: ... _T ...)` (signature
and body names disagreeing) and left the module TypeVar. I reverted it, wrote the PEP 695
headers by hand, deleted the now-unused module TypeVar/ParamSpec definitions, and let ruff
clean imports; a second ruff pass then normalised the underscore-prefixed names. mypy is green.

<!-- fr:journal kind=discovery scope=plan id=py314-format-churn created=2026-11-20T08:29:30+00:00 phase=1 -->
### py314-format-churn · discovery · ruff format at target py314 rewrites 98 files (PEP 758 unparenthesised except lists) (phase 1)

`except (A, B):` becomes `except A, B:` at py314, so `ruff format --check` at the new
target needs that mechanical churn (formatting only; legacy/pin tests rerun green).

<!-- fr:journal kind=discovery scope=plan id=ci-evidence-main-push-row created=2026-11-20T08:29:30+00:00 phase=1 -->
### ci-evidence-main-push-row · discovery · ci-single-leg-main-push stays walk-owed (phase 1)

Post-merge walk by design (spec Verification); not touched.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-20T08:29:30+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

the T1.S3 fix (PEP 695 generics, dropped TypeVars) is the cleanup; nothing further to tidy

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-20T08:29:30+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

a one-string image tag change in three places; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-20T08:29:30+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

rows, notes and fragment only; nothing to clean

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-20T08:38:03+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Amended rows ci-coverage-newest-leg and ci-shards-complete keep stale two-leg notes (phase 1)

docs/acceptance/features/2026-11-01-ci-speed.yaml:40,54.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-20T08:38:03+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · ci.yml comment claims --cov-report= cancels addopts' term-missing (phase 1)

.github/workflows/ci.yml:115-116; addopts is cleared by -o, and pytest-cov accumulates --cov-report values.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-20T08:38:03+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · test_ci_tests_one_python_the_floor checks only test/collect, not every ci.yml job (R3) (phase 1)

tests/unit/test_ci_python_floor.py:54.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-20T08:38:03+00:00 phase=1 state=open review_scope=out -->
### p1-r4 · finding [open] (reviewer: out of scope) · test_ci_shards.py:4 docstring still says 6-way matrix (phase 1)

Stale since gh#1428 (7 shards), before this change.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-20T08:38:03+00:00 phase=1 state=open review_scope=out -->
### p1-r5 · finding [open] (reviewer: out of scope) · scripts/floors.py keeps dead 3.11 tokenizer compatibility (phase 1)

scripts/floors.py:32-38; harmless, a follow-up cleanup.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-20T08:38:03+00:00 phase=1 state=open review_scope=out -->
### p1-r6 · finding [open] (reviewer: out of scope) · Other workflows set no UV_PYTHON, so uv downloads 3.14 every run (phase 1)

acceptance-report.yml, pages.yml, ci-budget.yml, pinned-clis.yml; correct, only slower.

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-20T08:38:03+00:00 phase=1 -->
### review-p1-1 · review · independent code review of phase 1: 6 findings (3 in, 3 out) (phase 1)

Reviewer verified the except reformat is purely syntactic (150 pairs, no `as` clauses), PEP 695 conversions keep bounds/variance, uv.lock moves no versions, acceptance anchors resolve, rewritten tests assert real shape. p1-r1..r3 fixed (r3 proven red against a mutated ci.yml with a typecheck-job UV_PYTHON); p1-r4..r6 out of scope.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-20T08:38:03+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Amended rows ci-coverage-newest-leg and ci-shards-complete keep stale two-leg notes (phase 1)

set-status amendments on both rows replace the two-leg notes (feature 2026-11-20-ci-single-python); fr acceptance check passes.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-20T08:38:03+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: ci.yml comment claims --cov-report= cancels addopts' term-missing (phase 1)

Comment now says addopts is cleared because pytest-cov accumulates --cov-report values; --cov-report= asks for no report.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-20T08:38:03+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: test_ci_tests_one_python_the_floor checks only test/collect, not every ci.yml job (R3) (phase 1)

The test loops over every ci.yml job: no python matrix, no job- or step-level UV_PYTHON, no setup-python. Red on a mutated ci.yml, green on the real one.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-20T08:38:03+00:00 phase=1 state=open resolves=p1-r4 out_of_scope=true -->
### p1-r4-resolved · finding [out-of-scope] · resolves p1-r4: test_ci_shards.py:4 docstring still says 6-way matrix (phase 1)

Pre-existing since gh#1428; this change did not cause it.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-20T08:38:03+00:00 phase=1 state=open resolves=p1-r5 out_of_scope=true -->
### p1-r5-resolved · finding [out-of-scope] · resolves p1-r5: scripts/floors.py keeps dead 3.11 tokenizer compatibility (phase 1)

Pre-existing compatibility code that stays correct; removal is an unrelated cleanup.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-20T08:38:03+00:00 phase=1 state=open resolves=p1-r6 out_of_scope=true -->
### p1-r6-resolved · finding [out-of-scope] · resolves p1-r6: Other workflows set no UV_PYTHON, so uv downloads 3.14 every run (phase 1)

Pre-existing: those workflows never pinned an interpreter; behaviour stays correct under the new floor.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-20T08:43:07+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · test_ci_tests_one_python_the_floor does not reject setup-uv `with: python-version`

tests/unit/test_ci_python_floor.py:54-64; a setup-uv step pinned to another interpreter would pass.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-20T08:43:07+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · release.yml's floor is checked only at workflow env

tests/unit/test_ci_python_floor.py:50-51; row ci-floor-python-3-14 claims the release suite runs on the floor (R6).

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-20T08:43:07+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · Row ci-scaffold-python-3-14 cites whole test files, not the golden comparisons

docs/acceptance/features/2026-11-20-ci-single-python.yaml:63-64.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-20T08:43:07+00:00 -->
### lens-review-1 · review · lens review: docs-accuracy (no findings), tests (3 in-scope findings)

docs-accuracy: every substantive page edit checked against scaffold.py, the pyproject files, install.sh and release.yml; none. tests: l-tests-r1..r3 fixed; the one-python test is now parametrized over ci.yml and release.yml and refuses setup-uv python-version, proven red by a mutated setup-uv step in each workflow.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-20T08:43:07+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: test_ci_tests_one_python_the_floor does not reject setup-uv `with: python-version`

test_one_python_the_floor refuses `python-version` in any step's `with`; red on a mutated ci.yml setup-uv step.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-20T08:43:07+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: release.yml's floor is checked only at workflow env

The same test is parametrized over release.yml (its test job must exist); red on a mutated release.yml setup-uv step.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-20T08:43:07+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: Row ci-scaffold-python-3-14 cites whole test files, not the golden comparisons

Row levels re-pointed to test_published_render_matches_the_golden and TestGoldenRenders::test_debt_on_matches_the_golden; ci-single-leg re-pointed to the renamed test; fr acceptance check passes.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved-2 created=2026-11-20T08:44:13+00:00 phase=1 state=open resolves=p1-r4 tracked_by=https://github.com/derio-net/super-fr/issues/1596 -->
### p1-r4-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1596] · resolves p1-r4: test_ci_shards.py:4 docstring still says 6-way matrix (phase 1)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1596.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved-2 created=2026-11-20T08:44:21+00:00 phase=1 state=open resolves=p1-r5 tracked_by=https://github.com/derio-net/super-fr/issues/1597 -->
### p1-r5-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1597] · resolves p1-r5: scripts/floors.py keeps dead 3.11 tokenizer compatibility (phase 1)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1597.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved-2 created=2026-11-20T08:44:29+00:00 phase=1 state=open resolves=p1-r6 tracked_by=https://github.com/derio-net/super-fr/issues/1598 -->
### p1-r6-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1598] · resolves p1-r6: Other workflows set no UV_PYTHON, so uv downloads 3.14 every run (phase 1)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1598.
