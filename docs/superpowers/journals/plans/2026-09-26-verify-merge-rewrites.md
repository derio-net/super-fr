# Journal: 2026-09-26-verify-merge-rewrites

<!-- fr:journal kind=discovery scope=plan id=verify-merge-mypy-flake created=2026-09-26T15:46:38 phase=1 -->
### verify-merge-mypy-flake · discovery · full-workspace mypy crashed once with INTERNAL ERROR (phase 1)

The first full-workspace mypy run after the edit hit an INTERNAL ERROR (mypy 1.20.0, exit 2); rerunning packages/fr/src alone and the full set again passed, and the pre-change tree also passes. Treated as a cache flake, not a code defect.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-26T15:46:38 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

Task 1 only adds failing tests; there was no production code to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-26T15:46:38 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

Task 3 is a matrix status move, a change fragment and a verification run; nothing to refactor.
