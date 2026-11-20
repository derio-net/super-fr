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
