<!-- fr:journal-schema=3 -->
# Journal: 2026-11-12-landing-front-page

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-12T07:57:11+00:00 input=true -->
### operator-brief · discovery · The operator's brief, verbatim

the explainers pages need to be improved. We recently made its creation mechanic and consistent. But it reads as a wiki. I want a front page that can draw users. See this, as inspiration, not to copy: https://www.example.com/product/how-it-works#overview (a third-party product page, address redacted)

<!-- fr:journal kind=decision scope=spec id=q1-build-route created=2026-11-12T07:57:11+00:00 decided_by=operator -->
### q1-build-route · decision · Front page built by an own landing template

Operator chose: scripts/build-site.py renders the front page itself from a template in this repo; other pages keep the blog-craft renderer. Rejected: staying in broadsheet Markdown only; a new style in blog-craft.

<!-- fr:journal kind=decision scope=spec id=q2-old-essay created=2026-11-12T07:57:11+00:00 decided_by=operator -->
### q2-old-essay · decision · The current essay is kept as its own explainer

Operator chose: the essay moves to its own page, linked from the front page. Rejected: folding it in; deleting it.

<!-- fr:journal kind=decision scope=spec id=q3-audience-cta created=2026-11-12T07:57:11+00:00 decided_by=operator -->
### q3-audience-cta · decision · Audience evaluators, primary CTA how it works

Operator chose: tech leads deciding whether to trust agents; primary button to the fr-goal explainer, install secondary. Not the recommended option (agent users, Install first).

<!-- fr:journal kind=decision scope=spec id=q4-structure created=2026-11-12T07:57:11+00:00 decided_by=operator -->
### q4-structure · decision · Hero plus numbered guarantee sections

Operator chose: hero and CTA, a how-a-run-goes strip, six to eight numbered sections (problem, headline, gain, how, link), all pages, closing CTA.

<!-- fr:journal kind=decision scope=spec id=q5-look created=2026-11-12T07:57:11+00:00 decided_by=operator -->
### q5-look · decision · Broadsheet identity at landing scale

Operator chose: reuse the broadsheet fonts, colours and accent; follow the reader's light or dark setting.

<!-- fr:journal kind=decision scope=spec id=q6-scope created=2026-11-12T07:57:11+00:00 decided_by=operator -->
### q6-scope · decision · Front page plus a shared top bar

Operator chose: the new front page and one small header on every built page; page text is not rewritten.

<!-- fr:journal kind=decision scope=spec id=q7-verification created=2026-11-12T07:57:11+00:00 decided_by=operator -->
### q7-verification · decision · CI and screenshots, gate developer

Operator chose: unit tests, the CI site build and screenshots pre-merge; one post-merge Test Plan row; gate developer, which holds nothing.

<!-- fr:journal kind=decision scope=spec id=q8-models created=2026-11-12T07:57:11+00:00 decided_by=operator -->
### q8-models · decision · Model per tier: haiku, sonnet, opus

old: unbound (mechanical, standard, hard); new: haiku, sonnet, opus on claude-code; reason: unbound; decider: operator; applied with fr models set.

<!-- fr:journal kind=decision scope=spec id=shape-light created=2026-11-12T07:57:11+00:00 decided_by=operator -->
### shape-light · decision · Run on fr-goal-light

The asks (landing renderer, essay move, top bar) are one reviewable change to scripts/build-site.py and the front-page source, planned as one agentic phase.

<!-- fr:journal kind=finding scope=spec id=r1 created=2026-11-12T08:04:22+00:00 state=open review_scope=in -->
### r1 · finding [open] (reviewer: in scope) · python-markdown is not installed in the test environment, so render_landing cannot be unit-tested as planned

target: spec. build-site.py imports only yaml; markdown exists only in the isolated deploy/site-build env (pages.yml:50, ci.yml:342), not in the pytest env that loads build-site.py (test_build_site.py:19). A top-level import would break every existing test.

<!-- fr:journal kind=finding scope=spec id=r2 created=2026-11-12T08:04:22+00:00 state=open review_scope=in -->
### r2 · finding [open] (reviewer: in scope) · Plan renames the essay's title; spec D said why-fr.md keeps it

target: plan. Spec D vs plan P1.T1.S2; docs/explainers/index.md:2.

<!-- fr:journal kind=finding scope=spec id=r3 created=2026-11-12T08:04:22+00:00 state=open review_scope=in -->
### r3 · finding [open] (reviewer: in scope) · R9's list of refusals is missing refusals the design and plan build

target: spec. layout: landing off index.html, a malformed flow section and a pages section with no marker were built but not listed in R9.

<!-- fr:journal kind=finding scope=spec id=r4 created=2026-11-12T08:04:22+00:00 state=open review_scope=in -->
### r4 · finding [open] (reviewer: in scope) · The build writes renderer output straight into out_dir, so 'writes no degraded page' cannot hold as worded

target: plan. scripts/build-site.py:357-359 passes the final target as -o and check_rendered runs after the file is written.

<!-- fr:journal kind=finding scope=spec id=r5 created=2026-11-12T08:04:22+00:00 state=open review_scope=in -->
### r5 · finding [open] (reviewer: in scope) · The placeholder index.md fails the question-round tripwire unless it mentions a round

target: plan. tests/unit/test_tripwire_fr_goal_question_rounds.py:162-167, :251-255.

<!-- fr:journal kind=finding scope=spec id=r6 created=2026-11-12T08:04:22+00:00 state=open review_scope=in -->
### r6 · finding [open] (reviewer: in scope) · README 'Start here' still points at index.html for the essay's content

target: plan. README.md:128 is an absolute site URL a grep for index.md misses; docs/explainers/fr-isolation.md:181.

<!-- fr:journal kind=finding scope=spec id=r7 created=2026-11-12T08:04:22+00:00 state=open review_scope=in -->
### r7 · finding [open] (reviewer: in scope) · docs-currency.md's covers does not include scripts/site/**

target: spec. docs/docs-currency.md:9-16.

<!-- fr:journal kind=finding scope=spec id=r8 created=2026-11-12T08:04:22+00:00 state=open review_scope=in -->
### r8 · finding [open] (reviewer: in scope) · The dark palette is hand-copied while the fonts are extracted, so it can drift from the renderer pin

target: spec. Spec B and R6; plan P1.T3.S2.

<!-- fr:journal kind=finding scope=spec id=r9 created=2026-11-12T08:04:22+00:00 state=open review_scope=in -->
### r9 · finding [open] (reviewer: in scope) · A committed red test spans task 4, and task 1 has no refactor step or reason

target: plan. P1.T4.S1/S2; task 1.

<!-- fr:journal kind=review scope=spec id=spec-plan-review-1 created=2026-11-12T08:04:22+00:00 -->
### spec-plan-review-1 · review · independent spec+plan review: 9 findings

Decisions q1-q8 and shape-light are honoured by the spec; the Test Plan heading is exact; the plan has one agentic phase linking every non-live row. Nine findings raised (r1-r9), all in scope; every named file, function, test and workflow was verified with file:line.

<!-- fr:journal kind=finding scope=spec id=r1-resolved created=2026-11-12T08:04:22+00:00 state=fixed resolves=r1 -->
### r1-resolved · finding [fixed] · resolves r1: python-markdown is not installed in the test environment, so render_landing cannot be unit-tested as planned

Spec A: build-site.py imports markdown lazily inside the build and every landing function takes the converter (to_html); tests pass a stand-in and assert on structure only. Plan P1.T3 says the same.

<!-- fr:journal kind=finding scope=spec id=r2-resolved created=2026-11-12T08:04:22+00:00 state=fixed resolves=r2 -->
### r2-resolved · finding [fixed] · resolves r2: Plan renames the essay's title; spec D said why-fr.md keeps it

Spec D now states the retitle to 'Why fr: the trustworthy agent' and why; plan unchanged.

<!-- fr:journal kind=finding scope=spec id=r3-resolved created=2026-11-12T08:04:22+00:00 state=fixed resolves=r3 -->
### r3-resolved · finding [fixed] · resolves r3: R9's list of refusals is missing refusals the design and plan build

R9 now lists layout-off-index, a run strip that is not one ordered list, and a page-list section without its marker.

<!-- fr:journal kind=finding scope=spec id=r4-resolved created=2026-11-12T08:04:22+00:00 state=fixed resolves=r4 -->
### r4-resolved · finding [fixed] · resolves r4: The build writes renderer output straight into out_dir, so 'writes no degraded page' cannot hold as worded

Spec C and plan P1.T4: pages render into a temp dir, are checked and given the bar, and only then written; a build-level test asserts no file is left at a refused route.

<!-- fr:journal kind=finding scope=spec id=r5-resolved created=2026-11-12T08:04:22+00:00 state=fixed resolves=r5 -->
### r5-resolved · finding [fixed] · resolves r5: The placeholder index.md fails the question-round tripwire unless it mentions a round

Plan P1.T1.S2: the placeholder carries a sentence naming the one question round.

<!-- fr:journal kind=finding scope=spec id=r6-resolved created=2026-11-12T08:04:22+00:00 state=fixed resolves=r6 -->
### r6-resolved · finding [fixed] · resolves r6: README 'Start here' still points at index.html for the essay's content

Spec D and plan P1.T1.S2 name README's Start-here link (to why-fr.html) and keep fr-isolation.md's overview link on index.md, with the reason.

<!-- fr:journal kind=finding scope=spec id=r7-resolved created=2026-11-12T08:04:22+00:00 state=fixed resolves=r7 -->
### r7-resolved · finding [fixed] · resolves r7: docs-currency.md's covers does not include scripts/site/**

Spec F and plan P1.T6.S1: scripts/site/** added to docs-currency.md's covers.

<!-- fr:journal kind=finding scope=spec id=r8-resolved created=2026-11-12T08:04:22+00:00 state=fixed resolves=r8 -->
### r8-resolved · finding [fixed] · resolves r8: The dark palette is hand-copied while the fonts are extracted, so it can drift from the renderer pin

R6, spec B and plan P1.T3: the dark :root block is extracted from a rendered page (extract_theme_css) like the fonts; landing.css holds only the light set and layout.

<!-- fr:journal kind=finding scope=spec id=r9-resolved created=2026-11-12T08:04:22+00:00 state=fixed resolves=r9 -->
### r9-resolved · finding [fixed] · resolves r9: A committed red test spans task 4, and task 1 has no refactor step or reason

The repo-level index test moved to task 5's RED; task 1 states its refactor reason.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-12T08:04:22+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  site-front-page-landing: none
  site-front-page-published: tester
  site-landing-build-refuses-malformed: none
  site-top-bar-every-page: none
  site-why-fr-essay-kept: none
row_kinds:
  site-front-page-landing: none
  site-front-page-published: live
  site-landing-build-refuses-malformed: none
  site-top-bar-every-page: none
  site-why-fr-essay-kept: none
run_gate: developer
run_kind: candidate
```

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-1 created=2026-11-12T12:10:18+00:00 -->
### test-plan-step-1 · discovery · Test Plan step 1: ran

Step: [developer] After merge, wait for the "Deploy explainers to Pages" run on `main`. Open `https://derio-net.github.io/super-fr/`: the landing page loads with its hero; the primary button opens the fr-goal explainer; the top bar on that explainer returns to the front page; `#explainers` lists every page; `/why-fr.html` and `/acceptance/` load.

Evidence: Walked the published site in a browser on 2026-11-12 after the Pages deploy (last-modified 11:32 GMT): the landing loads with its hero and top bar; the primary button opens 01-fr-goal.html; the bar site name returns to index.html; all 30 internal links on the front page, including every page-list entry, why-fr.html and acceptance/, return 200.
