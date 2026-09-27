# Journal: 2026-09-27-spec-ref-writers

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-27T10:08:00+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

The escape check is a 3-line os.path.normpath/commonpath guard placed inline in canonical_spec_ref, right beside the existing cross-repo-notation check it mirrors in shape and size — extracting it into a private helper would add a name and a call site without making either branch clearer.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-27T10:08:00+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

The fix is the one-line change the spec itself calls for (store refs.canonical_spec_ref(v1plan.spec, repo_root) instead of the verbatim v1 value); refs is already imported and repo_root already in scope, so there was nothing else nearby to clean up.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-09-27T10:08:00+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

Task 4 has no code steps of its own — it is the change fragment, acceptance-row moves, and quality gates (ruff/mypy/pytest/fr validate artifacts) that close out the phase, all of which ran clean the first time. Nothing to refactor.
