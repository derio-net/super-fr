# Journal: 2026-09-27-spec-ref-writers

<!-- fr:journal kind=decision scope=spec id=escape-test-lexical created=2026-09-27T09:43:28+00:00 -->
### escape-test-lexical · decision · #709: a spec: ref escapes the repo by a lexical normpath test

Operator chose os.path.normpath(repo_root / value) not under repo_root over Path.resolve(): it judges what the operator wrote, and a symlinked docs/ inside the repo still canonicalizes.

<!-- fr:journal kind=decision scope=spec id=archive-repair-single-owner created=2026-09-27T09:43:28+00:00 -->
### archive-repair-single-owner · decision · #710: fr archive repairs through one helper, once

Operator chose to strip repair out of _report_sweep and route both the archive tail and --sweep-only (when something moved) through one _repair_in_passing helper, over returning a RepairResult from _report_sweep.

<!-- fr:journal kind=decision scope=spec id=acceptance-two-rows created=2026-09-27T09:43:28+00:00 -->
### acceptance-two-rows · decision · Two acceptance rows, ci-pinned by this change's tests

spec-writers-one-canonical-form and archive-repair-warns-once.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-27T09:50:48+00:00 -->
### spec-review · review · independent spec review: 0 findings | clean

fr-spec-reviewer (separate context, sonnet) traced canonical_spec_ref's four branches (refs.py:139-153) against the new lexical escape check; confirmed the double repair (archive_cmd.py:64 and :238) and that --sweep-only returns before the tail (:107-122); confirmed migrate.py:278 stores v1plan.spec verbatim while :357 resolves the table row from v1plan.spec directly; confirmed repair._repair_meta and plan_ops :226/:396/:803 inherit the fix with no edit; confirmed the only_plans widening (:224-232) is independent of _report_sweep's signature; no test in test_archive_cmd.py calls _report_sweep or counts repaired:/warning: lines; every production repo_root is resolved and absolute, and os.path.commonpath is component-wise (rejects /tmp/repo2 vs /tmp/repo). No in-scope or out-of-scope findings.
