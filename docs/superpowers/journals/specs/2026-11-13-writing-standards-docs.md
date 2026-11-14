<!-- fr:journal-schema=4 -->
# Journal: 2026-11-13-writing-standards-docs

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-13T21:36:33+00:00 input=true -->
### brief · discovery · Operator brief (verbatim)

Earlier turn: "What about a blog-craft feature that uses STE as another writing method and we use it in super-fr afterwards to regenerate the explainers/documentation?"

This turn: "yes, let's bring the writing standards to super-fr, now. I closed #106, can you bring the isolation down before proceeding?"

<!-- fr:journal kind=decision scope=spec id=d-standards created=2026-11-13T21:40:25+00:00 decided_by=operator -->
### d-standards · decision · Guides and reference follow ste; explainers plain-language; why-fr elements-of-style; landing page none

Operator chose the recommended mapping.

_`decided_by=operator` recorded unverified: the gate could not read who answered it._

<!-- fr:journal kind=decision scope=spec id=d-scope created=2026-11-13T21:40:25+00:00 decided_by=operator -->
### d-scope · decision · Rewrite every page in this feature, explainers' warnings included; CI fails on any FAIL

Operator chose the full rewrite over failures-only or gate-only.

_`decided_by=operator` recorded unverified: the gate could not read who answered it._

<!-- fr:journal kind=decision scope=spec id=d-verification created=2026-11-13T21:40:25+00:00 decided_by=operator -->
### d-verification · decision · CI plus per-page fact checks; strategy none; no post-merge gate

Checker in site-build fails the PR on FAIL; each page passes --preserve-from origin/main and a fact-keeper review recorded in the plan journal.

_`decided_by=operator` recorded unverified: the gate could not read who answered it._

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-11-13T21:47:30+00:00 -->
### spec-review · review · independent spec review: 8 findings, all in scope

fr-spec-reviewer, read-only, separate context: checked the spec against decisions d-standards, d-scope, d-verification and the code it names (ci.yml site-build, build-site.py landing parser, fr.docs parse_page, blog-craft checker, tripwire tests, change-fragment rules). Suggested a tests lens.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-11-13T21:47:30+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · cli.md's generated cli-tree block cannot pass ste without changing fr help text

Raised by the spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-11-13T21:47:30+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · site-build gives PyYAML only to the build step's isolated env

Raised by the spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-11-13T21:47:30+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · explainers-currency.md edit needs its .opencode mirror regenerated

Raised by the spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-11-13T21:47:30+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · --preserve-from origin/main baseline moves during the feature

Raised by the spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-11-13T21:47:30+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · R8 ignored fact-keeper's added facts

Raised by the spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-11-13T21:47:30+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · rewrite must keep wording-pinning tripwires

Raised by the spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-11-13T21:47:30+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · R7 'no hit' vs kept warnings; front matter keys vs R3

Raised by the spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-11-13T21:47:30+00:00 state=open review_scope=in -->
### s8 · finding [open] (reviewer: in scope) · Test Plan gaps for R10 and R9's record; approval stop replacement unstated

Raised by the spec reviewer.

<!-- fr:journal kind=finding scope=spec id=s1-help-lines created=2026-11-13T21:47:30+00:00 state=open review_scope=out -->
### s1-help-lines · finding [open] (reviewer: out of scope) · fr's CLI help lines are too long for STE, so docs/reference/cli.md's generated tree cannot meet the guides' standard

Fixing it means rewriting fr's own help strings (a code change with a change fragment, a sync-readme regeneration and README table changes), outside this docs feature. cli.md opts out until then.

<!-- fr:journal kind=decision scope=spec id=d-cli-md-exception created=2026-11-13T21:47:30+00:00 -->
### d-cli-md-exception · decision · docs/reference/cli.md follows no standard (third exception), because its generated block mirrors fr's help text

Agent decision from spec finding s1, narrowing d-standards for one page; the alternative (rewriting fr's help strings) is a code change outside this feature's non-goals. Raised to the operator in the hand-off.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-13T21:47:30+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · 31 pages rewritten under wording-pinning tripwires plus a new CI step; the test plan relies on narrow checks

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-11-13T21:47:30+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: cli.md's generated cli-tree block cannot pass ste without changing fr help text

cli.md opts out (writing_standard: none) as a third recorded exception (R1, R3, §1); its hand-written prose is still rewritten; rewriting fr's help lines is filed as out-of-scope follow-up s1-help-lines.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-11-13T21:47:30+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: site-build gives PyYAML only to the build step's isolated env

Script runs the checker through `uv run --isolated --no-project --with pyyaml` from the repo root (R2, §1).

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-11-13T21:47:30+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: explainers-currency.md edit needs its .opencode mirror regenerated

R10 and §4 require scripts/sync-opencode.py and the regenerated mirror; Enforcement list names the new check; Test Plan 8.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-11-13T21:47:30+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: --preserve-from origin/main baseline moves during the feature

Baseline is the merge base, recorded once in the plan journal; pages main changed after a merge are re-checked (R7, §3 step 0).

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-11-13T21:47:30+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: R8 ignored fact-keeper's added facts

R8, §3 step 3 and Test Plan 5 cover lost, changed and added.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-11-13T21:47:30+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: rewrite must keep wording-pinning tripwires

New R12; §3 lists the tripwires; R7 keeps HTML comment markers; Test Plan 7.

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-11-13T21:47:30+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: R7 'no hit' vs kept warnings; front matter keys vs R3

R7 now 'no FAIL and no preserve hit', exempts R3's key and title/tldr prose; R9 covers every standard.

<!-- fr:journal kind=finding scope=spec id=s8-resolved created=2026-11-13T21:47:30+00:00 state=fixed resolves=s8 -->
### s8-resolved · finding [fixed] · resolves s8: Test Plan gaps for R10 and R9's record; approval stop replacement unstated

Test Plan 6 and 8 added; §3 states the operator's decisions replace the per-batch approval stop.

<!-- fr:journal kind=finding scope=spec id=s1-help-lines-resolved created=2026-11-13T21:47:30+00:00 state=open resolves=s1-help-lines out_of_scope=true -->
### s1-help-lines-resolved · finding [out-of-scope] · resolves s1-help-lines: fr's CLI help lines are too long for STE, so docs/reference/cli.md's generated tree cannot meet the guides' standard

Not caused by this change: fr's help text predates it and is code this docs feature does not touch.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-13-writing-standards-docs-p2 created=2026-11-13T21:48:45+00:00 -->
### phase-split-2026-11-13-writing-standards-docs-p2 · decision · review-size: reference pages to STE are one reviewable rewrite batch

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-13-writing-standards-docs-p3 created=2026-11-13T21:48:47+00:00 -->
### phase-split-2026-11-13-writing-standards-docs-p3 · decision · review-size: the nine guides to STE

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-13-writing-standards-docs-p4 created=2026-11-13T21:48:48+00:00 -->
### phase-split-2026-11-13-writing-standards-docs-p4 · decision · review-size: first six explainers to plain language

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-13-writing-standards-docs-p5 created=2026-11-13T21:48:49+00:00 -->
### phase-split-2026-11-13-writing-standards-docs-p5 · decision · review-size: second six explainers to plain language

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-13-writing-standards-docs-p6 created=2026-11-13T21:48:51+00:00 -->
### phase-split-2026-11-13-writing-standards-docs-p6 · decision · ask: the CI gate (R6) lands last, after every page passes, with the two remaining pages

<!-- fr:journal kind=decision scope=spec id=d-accuracy created=2026-11-13T22:17:52+00:00 decided_by=operator -->
### d-accuracy · decision · Pages must be (and stay) accurate: accuracy pass before each rewrite, docs-accuracy lens after

Operator, asked whether the rewrite is based on the code or the prose: "yes, I want the documents to be (and stay) accurate". Adds R13-R16.

<!-- fr:journal kind=finding scope=spec id=s1-help-lines-resolved-2 created=2026-11-14T01:53:56+00:00 state=open resolves=s1-help-lines tracked_by=https://github.com/derio-net/super-fr/issues/1440 -->
### s1-help-lines-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1440] · resolves s1-help-lines: fr's CLI help lines are too long for STE, so docs/reference/cli.md's generated tree cannot meet the guides' standard

Filed at deliver as https://github.com/derio-net/super-fr/issues/1440.

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-1 created=2026-11-14T02:21:20+00:00 -->
### test-plan-step-1 · discovery · Test Plan step 1: ran

Step: `site-build` builds every page with the new pin and runs `scripts/check-writing-standards.sh .blog-craft`: no FAIL.

Evidence: CI site-build green on the merged PR head 7082ff0dd (run 43545039044): it built every page at blog-craft 3b0c7d0 and ran scripts/check-writing-standards.sh .blog-craft (no FAIL), then the real-checker test; locally on main c0fdbce the script prints WRITING STANDARD OK for both groups (16 + 14 checked, 0 FAIL).

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-2 created=2026-11-14T02:21:21+00:00 -->
### test-plan-step-2 · discovery · Test Plan step 2: ran

Step: The unit test of §5 passes.

Evidence: tests/unit/test_writing_standards_docs.py passes on main c0fdbce with BLOG_CRAFT_DIR set (13 tests incl. the real-checker test); in CI the unit tests pass in the test shards and site-build runs the real-checker test.
