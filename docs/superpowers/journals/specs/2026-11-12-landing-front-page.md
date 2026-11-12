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
