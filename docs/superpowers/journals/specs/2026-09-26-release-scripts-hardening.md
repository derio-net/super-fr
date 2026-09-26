# Journal: 2026-09-26-release-scripts-hardening

<!-- fr:journal kind=decision scope=spec id=d-widen-code created=2026-09-26T12:07:40 -->
### d-widen-code · decision · Widen requires_bump to plugins/*/skills, not the docs

Per gh#671 and the brief; rules stay super-fr only as AGENTS.md documents.

<!-- fr:journal kind=decision scope=spec id=d-fail-loud created=2026-09-26T12:07:40 -->
### d-fail-loud · decision · No [project].version raises ValueError, no first-match fallback

A fallback would reintroduce the defect on the unattended release path.

<!-- fr:journal kind=decision scope=spec id=gate-no-questions-brainstorm created=2026-09-26T12:07:40 -->
### gate-no-questions-brainstorm · decision · Operator gate `brainstorm` cleared without asking

Batch dispatch: the operator's brief already fixed every decision (anchor to [project]; widen code not docs for plugins/*/skills; uv run --no-project python; one phase; claude-sonnet-5 for every tier). No operator-owned choice remained.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-26T12:09:34 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Missing-[project]-version ValueError unreachable via write_version; 'before a byte is written' false across files

version_surfaces() already raises for a missing version via tomllib; the reachable guard is regex-mismatch (single-quoted). write_version writes file by file.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-26T12:09:34 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · [project] table bounding underspecified

Header regex rejects a trailing comment; 'next line starting with [' is cut short by nested-array lines.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-26T12:09:34 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · 2.C hedges on setup-uv

change-fragment job has only checkout (ci.yml:94-102); setup-uv step is definite.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-26T12:09:34 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · Acceptance row does not cite test_version_surfaces.py

Spec claimed all three test files were cited.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-09-26T12:09:34 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · requires_bump edge cases and rules handling implicit

Pin plugins/[^/]+/skills/ and negative cases.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-09-26T12:09:34 state=open review_scope=out -->
### s6 · finding [open] (reviewer: out of scope) · check-change-fragment.py docstring advertises plain python

Prose adjacent to the change; harmless.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-26T12:09:34 -->
### spec-review · review · independent spec review: 6 findings (5 in scope, 1 out)

Reviewer fr-spec-reviewer verified decisions honoured and every named file/line against the codebase; 5 in-scope findings fixed in the spec, 1 out-of-scope.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-26T12:09:34 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Missing-[project]-version ValueError unreachable via write_version; 'before a byte is written' false across files

Spec 2.A rewritten: guard covers regex-mismatch; all rewrites computed before any write; test uses single-quoted version.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-26T12:09:34 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: [project] table bounding underspecified

Spec 2.A specifies header/boundary regexes, trailing comment, nested-array and [project.urls] tests.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-26T12:09:34 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: 2.C hedges on setup-uv

Spec 2.C states the setup-uv step; tripwire asserts it.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-26T12:09:34 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: Acceptance row does not cite test_version_surfaces.py

Spec section 4 corrects the claim and adds a set-status --level ref for test_version_surfaces.py.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-09-26T12:09:34 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: requires_bump edge cases and rules handling implicit

Spec 2.B pins the regex and negative cases.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-09-26T12:09:34 state=open resolves=s6 out_of_scope=true -->
### s6-resolved · finding [out-of-scope] · resolves s6: check-change-fragment.py docstring advertises plain python

Stale docstring line is not caused by this change's defect; spec 2.C touches it in passing anyway.
