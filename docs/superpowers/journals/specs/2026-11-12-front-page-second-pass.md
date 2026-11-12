<!-- fr:journal-schema=3 -->
# Journal: 2026-11-12-front-page-second-pass

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-12T13:49:33+00:00 input=true -->
### brief · discovery · Operator brief for the second pass on the front page

"check the published site once the Pages deploy finishes. I'm looking at it but I'm not sure whether the front page is up to date. The DevOps and Tester Gates are relatively new features that are missing. As is the Wave Driver and its pages. I guess that's alright as we didn't discuss further than the one frontpage, which features matter and for whom but I think we could do a better job here. Also, use more diagrams and visualizations. I also find the first page not so catchy, it's pretty generic. I guess that's on me as I confirmed to use the blog-fr's layout but for a front-page we should get a bit more flashy and modern"

Then: "merged. Let's start with the second pass".

<!-- fr:journal kind=decision scope=spec id=q1-audience created=2026-11-12T13:49:33+00:00 decided_by=operator -->
### q1-audience · decision · Audience: both, in two acts

Act one sells a single trustworthy run to a developer; act two sells running a whole backlog (waves, gates, release) to a lead or operator. decider: operator.

<!-- fr:journal kind=decision scope=spec id=q2-lineup created=2026-11-12T13:49:33+00:00 decided_by=operator -->
### q2-lineup · decision · First-class sections added: exit gates (Tester + DevOps) and the wave driver

Isolation, question round and spec, and independent review stay. Acceptance matrix and cost audit were not picked. decider: operator.

<!-- fr:journal kind=decision scope=spec id=q3-visual created=2026-11-12T13:49:33+00:00 decided_by=operator -->
### q3-visual · decision · Visual direction: dark, technical, glowing

Near-black canvas, one vivid accent gradient, large tight sans headline, monospace details, terminal-style hero, glassy cards; light variant follows the visitor's setting. Article pages keep broadsheet. decider: operator.

<!-- fr:journal kind=decision scope=spec id=q4-demoted created=2026-11-12T13:49:33+00:00 decided_by=operator -->
### q4-demoted · decision · Acceptance matrix and cost audit move to a compact 'also included' grid

One row of small cards (acceptance matrix, cost audit, debugging, triage board, harnesses), each a line and a link. decider: operator.

<!-- fr:journal kind=decision scope=spec id=q5-motion created=2026-11-12T13:49:33+00:00 decided_by=operator -->
### q5-motion · decision · Motion: CSS-only animation

Animated diagrams and a typed-out terminal hero in CSS and SVG, off under reduced motion. No JavaScript. decider: operator.

<!-- fr:journal kind=decision scope=spec id=q6-diagrams created=2026-11-12T13:49:33+00:00 decided_by=operator -->
### q6-diagrams · decision · Diagrams: run pipeline, gate ledger, wave of batches, isolation boundary

All four, hand-authored inline SVG kept in this repo. decider: operator.

<!-- fr:journal kind=decision scope=spec id=q7-pages created=2026-11-12T13:49:33+00:00 decided_by=operator -->
### q7-pages · decision · New explainer pages: wave driver and exit gates

Two new pages; the exit-gates page links to the existing DevOps gate page for detail. decider: operator.

<!-- fr:journal kind=decision scope=spec id=q8-headline created=2026-11-12T13:49:33+00:00 decided_by=operator -->
### q8-headline · decision · Headline kept; the rest of the copy rewritten

Subline, facts and section copy are rewritten for the two-act story. decider: operator.

<!-- fr:journal kind=decision scope=spec id=q9-verification created=2026-11-12T13:49:33+00:00 decided_by=operator -->
### q9-verification · decision · Verification as in the first pass; gate developer

Unit tests in CI plus browser screenshots (dark, light, phone width, reduced motion) at implement, review and deliver. One post-merge row for the published site. Gate: developer, which holds nothing. decider: operator.

<!-- fr:journal kind=finding scope=spec id=r1 created=2026-11-12T13:55:22+00:00 state=open review_scope=in -->
### r1 · finding [open] (reviewer: in scope) · Design C's theme change contradicts the first-pass tests and leaves extract_theme_css with no caller

target: spec. Raised by the independent spec reviewer; see the review entry spec-review-1.

<!-- fr:journal kind=finding scope=spec id=r2 created=2026-11-12T13:55:22+00:00 state=open review_scope=in -->
### r2 · finding [open] (reviewer: in scope) · A figure marker 'anywhere' in a flow or guarantee body is refused by the existing shape parsers

target: spec. Raised by the independent spec reviewer; see the review entry spec-review-1.

<!-- fr:journal kind=finding scope=spec id=r3 created=2026-11-12T13:55:22+00:00 state=open review_scope=in -->
### r3 · finding [open] (reviewer: in scope) · Inlining both wide and narrow variants, and reusing figures, produces duplicate SVG ids

target: spec. Raised by the independent spec reviewer; see the review entry spec-review-1.

<!-- fr:journal kind=finding scope=spec id=r4 created=2026-11-12T13:55:22+00:00 state=open review_scope=in -->
### r4 · finding [open] (reviewer: in scope) · The literal-colour check misfires on url(#id), and misses SVG's default black fill

target: spec. Raised by the independent spec reviewer; see the review entry spec-review-1.

<!-- fr:journal kind=finding scope=spec id=r5 created=2026-11-12T13:55:22+00:00 state=open review_scope=in -->
### r5 · finding [open] (reviewer: in scope) · The raw HTML block needs blank lines around it, and the survival check is too weak

target: spec. Raised by the independent spec reviewer; see the review entry spec-review-1.

<!-- fr:journal kind=finding scope=spec id=r6 created=2026-11-12T13:55:22+00:00 state=open review_scope=in -->
### r6 · finding [open] (reviewer: in scope) · test_tripwire_explainers_fresh.py has no closed list to add the new pages to

target: spec. Raised by the independent spec reviewer; see the review entry spec-review-1.

<!-- fr:journal kind=finding scope=spec id=r7 created=2026-11-12T13:55:22+00:00 state=open review_scope=in -->
### r7 · finding [open] (reviewer: in scope) · R9, R12 and R13 have no proof in Verification or Design F; R8's reduced-motion rule is only screenshotted

target: spec. Raised by the independent spec reviewer; see the review entry spec-review-1.

<!-- fr:journal kind=finding scope=spec id=r8 created=2026-11-12T13:55:22+00:00 state=open review_scope=in -->
### r8 · finding [open] (reviewer: in scope) · The R7 contrast test is undefined for glass cards and gradient accents

target: spec. Raised by the independent spec reviewer; see the review entry spec-review-1.

<!-- fr:journal kind=finding scope=spec id=r9 created=2026-11-12T13:55:22+00:00 state=open review_scope=in -->
### r9 · finding [open] (reviewer: in scope) · The operator asked for a typed-out terminal hero; the spec fades lines in

target: spec. Raised by the independent spec reviewer; see the review entry spec-review-1.

<!-- fr:journal kind=finding scope=spec id=r10 created=2026-11-12T13:55:22+00:00 state=open review_scope=in -->
### r10 · finding [open] (reviewer: in scope) · Two front-page link targets are left undecided

target: spec. Raised by the independent spec reviewer; see the review entry spec-review-1.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-12T13:55:22+00:00 -->
### spec-review-1 · review · independent spec review: 10 findings

findings: r1, r2, r3, r4, r5, r6, r7, r8, r9, r10 (all in scope). The reviewer verified the spec's named files, functions and constants against the code with file:line references, and decisions q1-q9 against the requirements.

<!-- fr:journal kind=finding scope=spec id=r1-resolved created=2026-11-12T13:55:22+00:00 state=fixed resolves=r1 -->
### r1-resolved · finding [fixed] · resolves r1: Design C's theme change contradicts the first-pass tests and leaves extract_theme_css with no caller

Design C rewritten: the landing takes nothing from a renderer page; extract_theme_css, THEME_PROPERTIES, extract_font_css and the two parameters are removed, the landing uses system font stacks and embeds no font, and the tests that change are named.

<!-- fr:journal kind=finding scope=spec id=r2-resolved created=2026-11-12T13:55:22+00:00 state=fixed resolves=r2 -->
### r2-resolved · finding [fixed] · resolves r2: A figure marker 'anywhere' in a flow or guarantee body is refused by the existing shape parsers

Design B now says parse_landing lifts a figure marker before the shape checks, one figure per section, allowed in flow, guarantee and prose, refused elsewhere; R10 lists the refusals.

<!-- fr:journal kind=finding scope=spec id=r3-resolved created=2026-11-12T13:55:22+00:00 state=fixed resolves=r3 -->
### r3-resolved · finding [fixed] · resolves r3: Inlining both wide and narrow variants, and reusing figures, produces duplicate SVG ids

Every id in a figure file must carry the file's name as prefix; an unprefixed id is refused (Design B, R10).

<!-- fr:journal kind=finding scope=spec id=r4-resolved created=2026-11-12T13:55:22+00:00 state=fixed resolves=r4 -->
### r4-resolved · finding [fixed] · resolves r4: The literal-colour check misfires on url(#id), and misses SVG's default black fill

The colour check is defined over attributes, style attributes and style elements with url(#…) stripped first; figures.css sets inherited fill, stroke and color so an unclassed element is never default black.

<!-- fr:journal kind=finding scope=spec id=r5-resolved created=2026-11-12T13:55:22+00:00 state=fixed resolves=r5 -->
### r5-resolved · finding [fixed] · resolves r5: The raw HTML block needs blank lines around it, and the survival check is too weak

The article-page block is padded with blank lines; the survival check now requires the exact inserted svg text verbatim in the rendered page on both paths.

<!-- fr:journal kind=finding scope=spec id=r6-resolved created=2026-11-12T13:55:22+00:00 state=fixed resolves=r6 -->
### r6-resolved · finding [fixed] · resolves r6: test_tripwire_explainers_fresh.py has no closed list to add the new pages to

Design E now says the pages join the tripwire's subset assertion.

<!-- fr:journal kind=finding scope=spec id=r7-resolved created=2026-11-12T13:55:22+00:00 state=fixed resolves=r7 -->
### r7-resolved · finding [fixed] · resolves r7: R9, R12 and R13 have no proof in Verification or Design F; R8's reduced-motion rule is only screenshotted

Design F and Verification gain a unit test for R9, the structural reduced-motion test for R8, and name the phase reviewer for R12 and R13.

<!-- fr:journal kind=finding scope=spec id=r8-resolved created=2026-11-12T13:55:22+00:00 state=fixed resolves=r8 -->
### r8-resolved · finding [fixed] · resolves r8: The R7 contrast test is undefined for glass cards and gradient accents

Design C states the contrast model: opaque text and surface tokens, text only on those surfaces, each pair at 4.5:1; gradient text only on large text with each stop at 3:1.

<!-- fr:journal kind=finding scope=spec id=r9-resolved created=2026-11-12T13:55:22+00:00 state=fixed resolves=r9 -->
### r9-resolved · finding [fixed] · resolves r9: The operator asked for a typed-out terminal hero; the spec fades lines in

R8 and Design C now type the prompt lines with steps() and reveal the output lines in turn.

<!-- fr:journal kind=finding scope=spec id=r10-resolved created=2026-11-12T13:55:22+00:00 state=fixed resolves=r10 -->
### r10-resolved · finding [fixed] · resolves r10: Two front-page link targets are left undecided

Section 4 links 01-fr-goal.md; the harness card links ../reference/install.md.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-12T13:55:23+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  site-front-page-second-pass-published: tester
  site-landing-figures: none
  site-landing-look-and-motion: none
  site-landing-refuses-malformed-figures-and-acts: none
  site-landing-two-acts: none
  site-wave-driver-and-exit-gates-pages: none
row_kinds:
  site-front-page-second-pass-published: live
  site-landing-figures: none
  site-landing-look-and-motion: none
  site-landing-refuses-malformed-figures-and-acts: none
  site-landing-two-acts: none
  site-wave-driver-and-exit-gates-pages: none
run_gate: developer
run_kind: candidate
```
