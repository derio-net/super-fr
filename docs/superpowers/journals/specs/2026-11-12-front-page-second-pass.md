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
