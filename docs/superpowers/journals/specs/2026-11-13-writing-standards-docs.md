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
