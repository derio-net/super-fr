# Journal: 2026-09-26-plan-table-header

<!-- fr:journal kind=decision scope=spec id=d1-create-section created=2026-09-26T07:35:57 -->
### d1-create-section · decision · create appends the canonical Implementation Plans section when missing

gh#603 cheapest cut, pre-decided by the batch brief. Pre-flight stays read-only.

<!-- fr:journal kind=decision scope=spec id=d2-name-header created=2026-09-26T07:35:57 -->
### d2-name-header · decision · Every remaining table error names the canonical header

Built from one constant shared with migrate._ensure_spec_plan_row.

<!-- fr:journal kind=decision scope=spec id=gate-no-questions-brainstorm created=2026-09-26T07:35:57 -->
### gate-no-questions-brainstorm · decision · Operator gate `brainstorm` cleared without asking

Batch dispatch brief fixed the scope (gh#603 cheapest cut: create the section with the canonical header, name the header in every table error), branch, version 4.23.1 and model; no operator-owned decision remained.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-26T07:37:09 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · _append_spec_row is also called by rework; auto-creating the section there changes rework

Reviewer: creation belongs in create only.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-26T07:37:09 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · A second no-table error site is not covered by d2

plan_ops.py:477 duplicates :414.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-26T07:37:09 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · d3 claims one header definition, but the design leaves three

Derive cells and separator from one line.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-26T07:37:09 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · Test Plan gaps

Pre-flight read-only, idempotent re-run, rework, second no-table site, matrix rows.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-26T07:37:09 -->
### spec-review · review · independent spec review: 4 findings

Reviewer verified plan_ops.py:390-477, :216, :273, migrate.py:737-767 against the spec; all named symbols exist; 4 in-scope findings, all fixed in the spec.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-26T07:37:09 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: _append_spec_row is also called by rework; auto-creating the section there changes rework

d1/d2: creation only in create; _append_spec_row stays strict, rework unchanged and tested (item 6).

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-26T07:37:09 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: A second no-table error site is not covered by d2

d3: both no-table sites and the missing-section error use one hint builder; test item 4.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-26T07:37:09 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: d3 claims one header definition, but the design leaves three

d4: cells and separator derived from _CANONICAL_HEADER_LINE.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-26T07:37:09 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: Test Plan gaps

Test Plan items 2, 3, 4, 6 added; matrix rows called out.
