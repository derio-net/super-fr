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

<!-- fr:journal kind=finding scope=plan id=r2-f3 created=2026-09-26T23:39:59 phase=1 state=open review_scope=in -->
### r2-f3 · finding [open] (reviewer: in scope) · No test that a scoped archive canonicalizes the archived plan's own spec (phase 1)

Opus review. Added test_single_plan_archive_canonicalizes_the_archived_plans_own_spec.

<!-- fr:journal kind=finding scope=plan id=r2-f4 created=2026-09-26T23:40:01 phase=1 state=open review_scope=in -->
### r2-f4 · finding [open] (reviewer: in scope) · Spec had an empty duplicate Implementation Plans section (phase 1)

Opus review. Same as spec finding s2-2; removed in the spec re-review commit.

<!-- fr:journal kind=finding scope=plan id=r2-f5 created=2026-09-26T23:40:02 phase=1 state=open review_scope=in -->
### r2-f5 · finding [open] (reviewer: in scope) · This plan's own _meta.yaml stored a non-canonical spec: (phase 1)

Opus review. Repaired via repair_repo(only_plans={this plan}).

<!-- fr:journal kind=finding scope=plan id=r2-f6 created=2026-09-26T23:40:04 phase=1 state=open review_scope=in -->
### r2-f6 · finding [open] (reviewer: in scope) · _repair_meta resolved the spec ref twice (phase 1)

Opus review. canonical_spec_ref takes an optional pre-computed resolution.

<!-- fr:journal kind=finding scope=plan id=r2-f7 created=2026-09-26T23:40:06 phase=1 state=open review_scope=out -->
### r2-f7 · finding [open] (reviewer: out of scope) · A ref escaping the repo is shortened to a local spec (phase 1)

Opus review. Predates this change (repair already did it; readers resolve by slug).

<!-- fr:journal kind=finding scope=plan id=r2-f8 created=2026-09-26T23:40:08 phase=1 state=open review_scope=out -->
### r2-f8 · finding [open] (reviewer: out of scope) · Archive runs repair twice and can print warnings twice (phase 1)

Opus review. Pre-existing _report_sweep + tail double call.

<!-- fr:journal kind=finding scope=plan id=r2-f9 created=2026-09-26T23:40:09 phase=1 state=open review_scope=out -->
### r2-f9 · finding [open] (reviewer: out of scope) · v1-to-v2 migration writes spec: verbatim (phase 1)

Opus review. Legacy writer, untouched here.

<!-- fr:journal kind=review scope=plan id=r2-review-opus created=2026-09-26T23:40:11 phase=1 -->
### r2-review-opus · review · independent code re-review of phase 1 on claude-opus-5-5: 9 findings (phase 1)

Fresh-context Opus reviewer (agent a154d6fb3340dc945). 6 in scope (all fixed), 3 out of scope. The earlier Sonnet review r1-review stays recorded. No correctness bug in the main fix; call sites complete; mirrors in sync.

<!-- fr:journal kind=finding scope=plan id=r2-f1-resolved created=2026-09-26T23:40:13 state=fixed resolves=r2-f1 -->
### r2-f1-resolved · finding [fixed] · resolves r2-f1: fr repair stopped shortening ambiguous lifecycle-root full paths

fixed in the Opus-review commits

<!-- fr:journal kind=finding scope=plan id=r2-f2-resolved created=2026-09-26T23:40:15 state=fixed resolves=r2-f2 -->
### r2-f2-resolved · finding [fixed] · resolves r2-f2: rework_create is a third spec: writer with its own canonical form

fixed in the Opus-review commits

<!-- fr:journal kind=finding scope=plan id=r2-f3-resolved created=2026-09-26T23:40:17 state=fixed resolves=r2-f3 -->
### r2-f3-resolved · finding [fixed] · resolves r2-f3: No test that a scoped archive canonicalizes the archived plan's own spec

fixed in the Opus-review commits

<!-- fr:journal kind=finding scope=plan id=r2-f4-resolved created=2026-09-26T23:40:19 state=fixed resolves=r2-f4 -->
### r2-f4-resolved · finding [fixed] · resolves r2-f4: Spec had an empty duplicate Implementation Plans section

fixed in the Opus-review commits

<!-- fr:journal kind=finding scope=plan id=r2-f5-resolved created=2026-09-26T23:40:21 state=fixed resolves=r2-f5 -->
### r2-f5-resolved · finding [fixed] · resolves r2-f5: This plan's own _meta.yaml stored a non-canonical spec:

fixed in the Opus-review commits

<!-- fr:journal kind=finding scope=plan id=r2-f6-resolved created=2026-09-26T23:40:23 state=fixed resolves=r2-f6 -->
### r2-f6-resolved · finding [fixed] · resolves r2-f6: _repair_meta resolved the spec ref twice

fixed in the Opus-review commits

<!-- fr:journal kind=finding scope=plan id=r2-f7-resolved created=2026-09-26T23:40:25 state=open resolves=r2-f7 out_of_scope=true -->
### r2-f7-resolved · finding [out-of-scope] · resolves r2-f7: A ref escaping the repo is shortened to a local spec

pre-existing; not caused by this change

<!-- fr:journal kind=finding scope=plan id=r2-f8-resolved created=2026-09-26T23:40:27 state=open resolves=r2-f8 out_of_scope=true -->
### r2-f8-resolved · finding [out-of-scope] · resolves r2-f8: Archive runs repair twice and can print warnings twice

pre-existing; not caused by this change

<!-- fr:journal kind=finding scope=plan id=r2-f9-resolved created=2026-09-26T23:40:29 state=open resolves=r2-f9 out_of_scope=true -->
### r2-f9-resolved · finding [out-of-scope] · resolves r2-f9: v1-to-v2 migration writes spec: verbatim

pre-existing; not caused by this change

<!-- fr:journal kind=finding scope=plan id=r1-n1-resolved-2 created=2026-09-27T00:02:45 state=refuted resolves=r1-n1 -->
### r1-n1-resolved-2 · finding [refuted] · resolves r1-n1: Some tests are regression pins, pass before the fix

Closeout triage: regression pins that pass before the fix are intended by spec §4 (repo-wide paths must stay); not a defect, so no issue filed.

<!-- fr:journal kind=finding scope=plan id=r1-n2-resolved-2 created=2026-09-27T00:02:46 state=refuted resolves=r1-n2 -->
### r1-n2-resolved-2 · finding [refuted] · resolves r1-n2: opencode live integration tests fail in this environment

Closeout triage: not reproducible — tests/integration -k opencode passed 9/9 on origin/main @ 5cb4bc56 (2026-09-27); the phase-1 failure was environmental.

<!-- fr:journal kind=finding scope=plan id=r2-f7-resolved-2 created=2026-09-27T00:02:46 state=open resolves=r2-f7 tracked_by=#709 -->
### r2-f7-resolved-2 · finding [deferred → #709] · resolves r2-f7: A ref escaping the repo is shortened to a local spec

Filed at closeout as #709.

<!-- fr:journal kind=finding scope=plan id=r2-f8-resolved-2 created=2026-09-27T00:02:47 state=open resolves=r2-f8 tracked_by=#710 -->
### r2-f8-resolved-2 · finding [deferred → #710] · resolves r2-f8: Archive runs repair twice and can print warnings twice

Filed at closeout as #710.

<!-- fr:journal kind=finding scope=plan id=r2-f9-resolved-2 created=2026-09-27T00:02:48 state=open resolves=r2-f9 tracked_by=#711 -->
### r2-f9-resolved-2 · finding [deferred → #711] · resolves r2-f9: v1-to-v2 migration writes spec: verbatim

Filed at closeout as #711.
