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

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-09-27T10:18:59+00:00 phase=1 -->
### review-phase-1 · review · phase 1 code review: 3 findings (1 in scope, 2 out of scope) | ready to merge (phase 1)

Independent reviewer (separate context, sonnet) over f6d45f0d..HEAD against spec + plan. Confirmed all three fixes match spec §3.A-C, that each new test fails on pre-fix code (#709 same-slug local spec present; #710 asserts call count AND printed-once; #711 full path stored), and that --sweep-only still repairs repo-wide. Raised cr-1, cr-2, cr-3.

<!-- fr:journal kind=finding scope=plan id=cr-1 created=2026-09-27T10:18:59+00:00 phase=1 state=open review_scope=in -->
### cr-1 · finding [open] (reviewer: in scope) · canonical_spec_ref escape check raises ValueError on a relative repo_root with an absolute ref (phase 1)

refs.py: os.path.commonpath refuses to mix a relative root with an absolute target, so the new check (the only line in the function that can raise) crashed where the old code tolerated a relative repo_root. Unreachable from current callers (resolve_repo_root is absolute) but a regression in the one canonical definition.

<!-- fr:journal kind=finding scope=plan id=cr-2 created=2026-09-27T10:18:59+00:00 phase=1 state=open review_scope=out -->
### cr-2 · finding [open] (reviewer: out of scope) · repair._repair_meta warns 'ambiguous' before canonical_spec_ref decides to keep a ref verbatim (phase 1)

A repo-escaping ref whose slug matches same-named specs in two lifecycle roots gets an ambiguity warning about a ref left untouched.

<!-- fr:journal kind=finding scope=plan id=cr-3 created=2026-09-27T10:18:59+00:00 phase=1 state=open review_scope=out -->
### cr-3 · finding [open] (reviewer: out of scope) · the lexical escape check reads the raw value, so a backtick-annotated escaping ref is not caught (phase 1)

A value like `../sibling/specs/foo.md` (note) keeps its backtick through normpath, so it is not seen as escaping and could still be shortened to a same-slug local spec.

<!-- fr:journal kind=finding scope=plan id=cr-1-resolved created=2026-09-27T10:18:59+00:00 phase=1 state=fixed resolves=cr-1 -->
### cr-1-resolved · finding [fixed] · resolves cr-1: canonical_spec_ref escape check raises ValueError on a relative repo_root with an absolute ref (phase 1)

Escape check uses os.path.abspath for root and target (normalises as normpath did, and makes both absolute). Red-first test test_canonical_spec_ref_tolerates_a_relative_repo_root (ValueError before, green after).

<!-- fr:journal kind=finding scope=plan id=cr-2-resolved created=2026-09-27T10:18:59+00:00 phase=1 state=open resolves=cr-2 out_of_scope=true -->
### cr-2-resolved · finding [out-of-scope] · resolves cr-2: repair._repair_meta warns 'ambiguous' before canonical_spec_ref decides to keep a ref verbatim (phase 1)

Not caused by this change: the same warn-then-verbatim ordering already applied to the existing "exists outside SPEC_ROOTS" verbatim branch before #709; this change only adds another verbatim trigger. Reordering repair's warnings is its own change.

<!-- fr:journal kind=finding scope=plan id=cr-3-resolved created=2026-09-27T10:18:59+00:00 phase=1 state=open resolves=cr-3 out_of_scope=true -->
### cr-3-resolved · finding [out-of-scope] · resolves cr-3: the lexical escape check reads the raw value, so a backtick-annotated escaping ref is not caught (phase 1)

No spec: writer receives a decorated value: stored spec: fields are YAML scalars (repair), CLI arguments (plan create), a parsed _meta (rework) or the v1 **Spec:** value (migration); backticked annotations exist only in spec-table File cells, handled by a different path. The operator chose a lexical test of the written value (§2); extending it to token extraction is a separate change.

<!-- fr:journal kind=finding scope=plan id=cr-2-resolved-2 created=2026-09-27T18:26:02+00:00 state=open resolves=cr-2 tracked_by=#749 -->
### cr-2-resolved-2 · finding [deferred → #749] · resolves cr-2: repair._repair_meta warns 'ambiguous' before canonical_spec_ref decides to keep a ref verbatim

Filed at closeout as #749.
