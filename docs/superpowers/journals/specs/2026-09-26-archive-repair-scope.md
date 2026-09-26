# Journal: 2026-09-26-archive-repair-scope

<!-- fr:journal kind=decision scope=spec id=canonical-spec-form created=2026-09-26T15:09:01 -->
### canonical-spec-form · decision · Canonical spec: form is the bare filename

Operator chose bare <name>-design.md (lifecycle-independent). plan create normalizes to it; validator/resolver keep accepting the full path.

<!-- fr:journal kind=decision scope=spec id=repair-scope created=2026-09-26T15:09:01 -->
### repair-scope · decision · Single-plan archive repairs only the archived plan's rows

Operator chose an only_plans filter on repair_repo; --all, --sweep-only and fr repair stay repo-wide.

<!-- fr:journal kind=decision scope=spec id=no-test-plan created=2026-09-26T15:09:01 -->
### no-test-plan · decision · No post-merge Test Plan

Bug fix, CI tests only.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-26T15:10:34 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Scoped row match key ambiguous

Pinned to refs.plan_slug(file_cell); out-of-scope rows emit no warnings (spec 3.A).

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-26T15:10:34 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · Scoped meta lookup and slug source underspecified

Spec 3.A/3.B now state the glob filter and only_plans = names of archived paths.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-26T15:10:34 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · Create normalization guard

Spec 3.C: shared helper, value-only, shortens only when resolved file equals named file.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-26T15:10:34 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · Readers/tests inventory missing

Test plan 5-6 cover readers and updated create tests.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-09-26T15:10:34 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · Untested create cases

Test plan 3b and 4 extended.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-26T15:10:34 -->
### spec-review · review · independent spec review: 5 findings

5 in-scope findings, all fixed in the spec; verified file:line claims held.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-26T15:10:34 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Scoped row match key ambiguous

spec 3.A

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-26T15:10:34 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: Scoped meta lookup and slug source underspecified

spec 3.A/3.B

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-26T15:10:34 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: Create normalization guard

spec 3.C

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-26T15:10:34 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: Readers/tests inventory missing

spec 4 tests 5-6

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-09-26T15:10:34 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: Untested create cases

spec 4 tests 3b/4

<!-- fr:journal kind=review scope=spec id=spec-review-opus created=2026-09-26T23:36:02 -->
### spec-review-opus · review · independent spec re-review on claude-opus-5-5: 4 findings

Fresh-context Opus reviewer (agent a85d442d1deeaebef). 3 in scope, 1 out. The earlier Sonnet review 'spec-review' stays recorded. Prior s1-s5 fixes checked and correct, except the s3 wording, which produced s2-1.

<!-- fr:journal kind=finding scope=spec id=s2-1 created=2026-09-26T23:36:21 state=open review_scope=in -->
### s2-1 · finding [open] (reviewer: in scope) · §3.C strict same-file rule would stop fr repair fixing stale full paths

Opus spec review. Reworded §3.C to the implemented rule (keep verbatim only when the value names an existing different file; a moved spec still canonicalizes) and added a repair-level test-plan case.

<!-- fr:journal kind=finding scope=spec id=s2-2 created=2026-09-26T23:36:22 state=open review_scope=in -->
### s2-2 · finding [open] (reviewer: in scope) · Spec carried an empty duplicate Implementation Plans section

Opus spec review. Deleted the empty numbered section.

<!-- fr:journal kind=finding scope=spec id=s2-3 created=2026-09-26T23:36:23 state=open review_scope=in -->
### s2-3 · finding [open] (reviewer: in scope) · Canonical create output breaks #133 idempotent re-run of an old half-built folder

Opus spec review. Documented as an accepted edge in §3.C (operator deletes the stranded folder).

<!-- fr:journal kind=finding scope=spec id=s2-4 created=2026-09-26T23:36:23 state=open review_scope=out -->
### s2-4 · finding [open] (reviewer: out of scope) · fr migrate dirs also runs repair_repo repo-wide

Opus spec review. Pre-existing; a repo-level migration, repo-wide by intent; not named by the repair-scope decision.

<!-- fr:journal kind=finding scope=spec id=s2-1-resolved created=2026-09-26T23:36:24 state=fixed resolves=s2-1 -->
### s2-1-resolved · finding [fixed] · resolves s2-1: §3.C strict same-file rule would stop fr repair fixing stale full paths

spec edited in the Opus-review commit

<!-- fr:journal kind=finding scope=spec id=s2-2-resolved created=2026-09-26T23:36:25 state=fixed resolves=s2-2 -->
### s2-2-resolved · finding [fixed] · resolves s2-2: Spec carried an empty duplicate Implementation Plans section

spec edited in the Opus-review commit

<!-- fr:journal kind=finding scope=spec id=s2-3-resolved created=2026-09-26T23:36:26 state=fixed resolves=s2-3 -->
### s2-3-resolved · finding [fixed] · resolves s2-3: Canonical create output breaks #133 idempotent re-run of an old half-built folder

spec edited in the Opus-review commit
