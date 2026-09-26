# Journal: 2026-09-26-plan-table-header

<!-- fr:journal kind=discovery scope=plan id=p1-separator-unused created=2026-09-26T07:40:08 phase=1 -->
### p1-separator-unused · discovery · _CANONICAL_HEADER_SEPARATOR has no consumer yet (phase 1)

Added and derived from the header line per the plan, but nothing reads it until the phase that creates the section (_ensure_section_text) lands.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-26T07:40:08 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

the header literal now lives once (_CANONICAL_HEADER_LINE) with cells and separator derived from it; grep 'Depends on' in plan_ops.py shows a single literal, nothing further to clean

<!-- fr:journal kind=finding scope=plan id=r1-1 created=2026-09-26T07:40:50 phase=1 state=open review_scope=out -->
### r1-1 · finding [open] (reviewer: out of scope) · _CANONICAL_HEADER_SEPARATOR has no consumer yet (phase 1)

plan_ops.py:402; consumed by _ensure_section_text in phase 2 as planned.

<!-- fr:journal kind=finding scope=plan id=r1-2 created=2026-09-26T07:40:50 phase=1 state=open review_scope=out -->
### r1-2 · finding [open] (reviewer: out of scope) · migrate.py:761 still hard-codes the header (phase 1)

Spec d4 assigns it to phase 2 task S3.

<!-- fr:journal kind=finding scope=plan id=r1-3 created=2026-09-26T07:40:50 phase=1 state=open review_scope=out -->
### r1-3 · finding [open] (reviewer: out of scope) · test _HEADER duplicates the literal (phase 1)

Deliberate pin so the tests are not tautological.

<!-- fr:journal kind=finding scope=plan id=r1-4 created=2026-09-26T07:40:50 phase=1 state=open review_scope=out -->
### r1-4 · finding [open] (reviewer: out of scope) · no spec no-mutation assertion in the no-table create test (phase 1)

Pre-flight raises before any write; the mismatch test already asserts the spec is untouched. Low risk.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-09-26T07:40:50 phase=1 -->
### review-p1 · review · phase 1 independent review: no in-scope defects (phase 1)

Reviewer confirmed one builder, single-line derivation, strict _append_spec_row and meaningful tests; ran the plan_ops suite (114 passed). 4 out-of-scope observations, all filed.

<!-- fr:journal kind=finding scope=plan id=r1-1-resolved created=2026-09-26T07:40:50 phase=1 state=open resolves=r1-1 out_of_scope=true -->
### r1-1-resolved · finding [out-of-scope] · resolves r1-1: _CANONICAL_HEADER_SEPARATOR has no consumer yet (phase 1)

Phase 2 adds its consumer; not a defect of phase 1.

<!-- fr:journal kind=finding scope=plan id=r1-2-resolved created=2026-09-26T07:40:50 phase=1 state=open resolves=r1-2 out_of_scope=true -->
### r1-2-resolved · finding [out-of-scope] · resolves r1-2: migrate.py:761 still hard-codes the header (phase 1)

Planned for phase 2; phase 1's scope was plan_ops.py.

<!-- fr:journal kind=finding scope=plan id=r1-3-resolved created=2026-09-26T07:40:50 phase=1 state=open resolves=r1-3 out_of_scope=true -->
### r1-3-resolved · finding [out-of-scope] · resolves r1-3: test _HEADER duplicates the literal (phase 1)

Intentional test pin, not a defect.

<!-- fr:journal kind=finding scope=plan id=r1-4-resolved created=2026-09-26T07:40:50 phase=1 state=open resolves=r1-4 out_of_scope=true -->
### r1-4-resolved · finding [out-of-scope] · resolves r1-4: no spec no-mutation assertion in the no-table create test (phase 1)

Covered indirectly; not caused by this change.

<!-- fr:journal kind=discovery scope=plan id=p2-tests-red-then-green created=2026-09-26T07:42:31 phase=2 -->
### p2-tests-red-then-green · discovery · create appends missing section; existing #133 preflight test replaced (phase 2)

test_create_preflight_validates_spec_before_creating_folder asserted the old missing-section refusal; replaced by tests for the new behaviour. _CANONICAL_HEADER_SEPARATOR now has a consumer (_ensure_section_text). migrate output byte-identical (test_v2_migrate unchanged, green).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-09-26T07:42:31 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

the refactor step (S3) was the cleanup: migrate._ensure_spec_plan_row now reuses plan_ops._ensure_section_text, leaving one header literal; nothing further to clean

<!-- fr:journal kind=finding scope=plan id=r2-1 created=2026-09-26T07:43:50 phase=2 state=open review_scope=in -->
### r2-1 · finding [open] (reviewer: in scope) · stale pre-flight comment in create (plan_ops.py:200) (phase 2)

Said a section-less spec must fail loud; it is now accepted and written.

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-09-26T07:43:50 phase=2 -->
### review-p2 · review · phase 2 independent review: 1 in-scope finding (phase 2)

Reviewer confirmed section written only when absent right before the strict append, read-only pre-flight, rework strict, migrate output byte-identical, no other consumer of the old refusal text; 200 tests passed. One stale comment, fixed.

<!-- fr:journal kind=finding scope=plan id=r2-1-resolved created=2026-09-26T07:43:50 phase=2 state=fixed resolves=r2-1 -->
### r2-1-resolved · finding [fixed] · resolves r2-1: stale pre-flight comment in create (plan_ops.py:200) (phase 2)

Comment rewritten to describe the malformed-table pre-flight and the create-writes-section behaviour.
