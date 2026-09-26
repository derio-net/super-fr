# Journal: 2026-09-26-archive-repair-scope

<!-- fr:journal kind=decision scope=plan id=canonical-spec-ref-lenient-on-moved-paths created=2026-09-26T15:51:05 phase=1 -->
### canonical-spec-ref-lenient-on-moved-paths · decision · canonical_spec_ref keeps repair's slug fallback for a path that no longer exists (phase 1)

The helper shortens to the bare filename unless the named path exists as a file different from the one slug resolution picks (same-name-different-path stays verbatim). A stale full path whose spec moved to implemented/specs/ still canonicalizes by slug, preserving repair's existing doctrine.

<!-- fr:journal kind=discovery scope=plan id=scoping-single-predicate created=2026-09-26T15:51:05 phase=1 -->
### scoping-single-predicate · discovery · Scoping lives in one _in_scope predicate; canonicalization in refs.canonical_spec_ref (phase 1)

T1.S3 and T2.S3 refactors were done as part of green: repair._in_scope is the sole scoping predicate, and _repair_meta delegates spec canonicalization to refs.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-26T15:51:05 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

docs/mirrors/fragment task; nothing to clean

<!-- fr:journal kind=finding scope=plan id=r1-f1 created=2026-09-26T15:52:53 phase=1 state=open review_scope=in -->
### r1-f1 · finding [open] (reviewer: in scope) · fr repair no longer rewrites a same-named spec at another path; no repair-level test (phase 1)

Intended per spec 3.C guard. Added test_repair_leaves_a_same_named_spec_at_another_path_alone.

<!-- fr:journal kind=finding scope=plan id=r1-f2 created=2026-09-26T15:52:53 phase=1 state=open review_scope=in -->
### r1-f2 · finding [open] (reviewer: in scope) · Missing full-path back-compat test (phase 1)

Added test_full_path_spec_ref_still_resolves. plan-config scoped skip covered for save_to; archive e2e for the archived plan's own row is covered at unit level by the scoped File-cell test.

<!-- fr:journal kind=finding scope=plan id=r1-n1 created=2026-09-26T15:52:53 phase=1 state=open review_scope=out -->
### r1-n1 · finding [open] (reviewer: out of scope) · Some tests are regression pins, pass before the fix (phase 1)

Intended by spec 4 (repo-wide paths must stay); not a defect.

<!-- fr:journal kind=finding scope=plan id=r1-n2 created=2026-09-26T15:52:53 phase=1 state=open review_scope=out -->
### r1-n2 · finding [open] (reviewer: out of scope) · opencode live integration tests fail in this environment (phase 1)

Diff touches nothing they exercise (no fr-opencode-plugin or gate code); environmental.

<!-- fr:journal kind=review scope=plan id=r1-review created=2026-09-26T15:52:53 phase=1 -->
### r1-review · review · independent code review of phase 1 (phase 1)

2 minor in-scope findings, both fixed with tests; 2 out-of-scope notes; call sites verified complete.

<!-- fr:journal kind=finding scope=plan id=r1-f1-resolved created=2026-09-26T15:52:53 phase=1 state=fixed resolves=r1-f1 -->
### r1-f1-resolved · finding [fixed] · resolves r1-f1: fr repair no longer rewrites a same-named spec at another path; no repair-level test (phase 1)

test added

<!-- fr:journal kind=finding scope=plan id=r1-f2-resolved created=2026-09-26T15:52:53 phase=1 state=fixed resolves=r1-f2 -->
### r1-f2-resolved · finding [fixed] · resolves r1-f2: Missing full-path back-compat test (phase 1)

test added

<!-- fr:journal kind=finding scope=plan id=r1-n1-resolved created=2026-09-26T15:52:53 phase=1 state=open resolves=r1-n1 out_of_scope=true -->
### r1-n1-resolved · finding [out-of-scope] · resolves r1-n1: Some tests are regression pins, pass before the fix (phase 1)

regression pins are intended by the spec; nothing this change caused

<!-- fr:journal kind=finding scope=plan id=r1-n2-resolved created=2026-09-26T15:52:53 phase=1 state=open resolves=r1-n2 out_of_scope=true -->
### r1-n2-resolved · finding [out-of-scope] · resolves r1-n2: opencode live integration tests fail in this environment (phase 1)

environmental opencode binary failure; diff does not touch what they exercise

<!-- fr:journal kind=finding scope=plan id=r2-f1 created=2026-09-26T23:39:56 phase=1 state=open review_scope=in -->
### r2-f1 · finding [open] (reviewer: in scope) · fr repair stopped shortening ambiguous lifecycle-root full paths (phase 1)

Opus review. Guard now applies only to existing files outside SPEC_ROOTS; test_repair_still_shortens_an_ambiguous_lifecycle_path.

<!-- fr:journal kind=finding scope=plan id=r2-f2 created=2026-09-26T23:39:58 phase=1 state=open review_scope=in -->
### r2-f2 · finding [open] (reviewer: in scope) · rework_create is a third spec: writer with its own canonical form (phase 1)

Opus review. Routed through canonical_spec_ref; test_rework_create_writes_the_same_canonical_spec_as_repair.
