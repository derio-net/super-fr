<!-- fr:journal-schema=3 -->
# Journal: 2026-11-12-review-lenses

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-12T15:54:50+00:00 input=true -->
### brief · discovery · Operator's brief, verbatim

How can we ship better code with super-fr? How can we sensibly use flows or steps in the existing flows to make the code more maintainable, readable, secure? An extra datapoint: https://evanxmerz.com/post/ai-usage-generates-a-fragile-codebase/

<!-- fr:journal kind=decision scope=spec id=d1-first-focus created=2026-11-12T15:54:50+00:00 decided_by=operator -->
### d1-first-focus · decision · Design review lenses first

Asked which of four quality areas to design first (review lenses, whole-change review, reuse search at plan time, operator comprehension). Operator chose review lenses. The other three are later specs.

<!-- fr:journal kind=decision scope=spec id=d2-lenses-per-phase created=2026-11-12T15:54:50+00:00 decided_by=operator -->
### d2-lenses-per-phase · decision · Lenses are chosen per phase in the plan

Asked how lenses are applied in a phase's review. Operator chose lenses named on the plan's phase header, checked by fr plan self-review, with one reviewer covering the named ones; not all lenses always, not one reviewer per lens.

<!-- fr:journal kind=decision scope=spec id=d3-waiver-plus-path-rules created=2026-11-12T15:54:50+00:00 decided_by=operator -->
### d3-waiver-plus-path-rules · decision · Every lens applied or waived with a reason, plus repo path rules

Asked what stops a phase under-declaring. Operator chose both: every agentic phase states each lens as applied or waived with a reason, and a repo may map path globs to mandatory lenses that a waiver does not satisfy.

<!-- fr:journal kind=decision scope=spec id=d4-four-shipped-repo-may-add created=2026-11-12T15:54:50+00:00 decided_by=operator -->
### d4-four-shipped-repo-may-add · decision · Four shipped lenses; a repo may add, replace and disable

Asked which lenses exist. Operator chose security, tests, simplicity and errors shipped by fr, with a repo file able to add lenses or replace a shipped lens's instruction text.

<!-- fr:journal kind=decision scope=spec id=d5-evidence-tied-to-files created=2026-11-12T15:54:50+00:00 decided_by=operator -->
### d5-evidence-tied-to-files · decision · Reviewer lines tied to changed files, checked by fr, shown in the PR

Asked what the reviewer returns per lens. Operator chose one line per declared lens naming changed files examined and finding ids; fr refuses the review resolve on a missing line, no file from the phase's diff, or an unknown finding id; the result is stored on the run and shown as a table in the PR body.

<!-- fr:journal kind=decision scope=spec id=d6-verification-candidate created=2026-11-12T15:54:50+00:00 decided_by=operator -->
### d6-verification-candidate · decision · Verified on a candidate build, all rows, no post-merge walk

The standing verification question. Operator chose the candidate strategy for every row, with a stubbed reviewer return in the scenarios; no gate holds the close-out.
