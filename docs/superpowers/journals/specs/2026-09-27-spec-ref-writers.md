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
