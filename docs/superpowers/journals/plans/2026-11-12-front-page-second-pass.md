<!-- fr:journal-schema=3 -->
# Journal: 2026-11-12-front-page-second-pass

<!-- fr:journal kind=discovery scope=plan id=p1-figure-order created=2026-11-12T14:13:44+00:00 phase=1 -->
### p1-figure-order · discovery · Task 1's green step needed a real figure, so the two figures were authored before it was green (phase 1)

P1.T1.S2 forbids a placeholder figure and names task 3's gate-ledger.svg as the first real one,
so the loader and the tests were written red first, then the figures, then green. One
test, test_every_property_the_site_stylesheets_use_is_a_required_theme_property, globbed every
stylesheet in scripts/site/, so the new figures.css (its own --fig-* vocabulary) is skipped in
that glob; phase 2 replaces the test.

<!-- fr:journal kind=discovery scope=plan id=p1-code-over-spec created=2026-11-12T14:13:44+00:00 phase=1 -->
### p1-code-over-spec · discovery · The explainers follow the code where the older specs differ (phase 1)

The wave-driver spec says the driver merges a ready pull request; the shipped driver also
requires the operator's approved-fr label and removes it when a foreign push moves the head.
The exit-gates spec says the post-merge gates hold only the close-out; gates.py also makes
devops hold the merge on the triage merge path (a merge in the forge UI is not blocked).
Both pages say what the code does.

<!-- fr:journal kind=discovery scope=plan id=p1-real-build created=2026-11-12T14:13:44+00:00 phase=1 -->
### p1-real-build · discovery · A real build with the pinned renderer keeps the figure verbatim (phase 1)

python-markdown passes the compacted figure block through unchanged; the survival check
passed on all 31 pages, and pages without a figure (fr-audit, fr-init, fr-isolation,
01-fr-goal) are byte-identical to a build of the base commit. docs-currency.md differs because
it gained a figures section. Screenshots at 1280 and 390 px show both figures drawn and legible
with no horizontal scroll; two overflowing text lines found there were fixed in the figures.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-12T14:13:44+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

hand-authored SVG assets; nothing to restructure

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-12T14:13:44+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

prose pages; no code to restructure

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-12T14:20:51+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · fr-wave-driver.md says a draft is never merged, but an approved green draft is marked ready and merged (phase 1)

batch_drive.py:1624, batch_merge.py:431-456.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-12T14:20:51+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · A figure with no narrow file gets class fig-wide, which figures.css hides at narrow widths, so it vanishes on phones (phase 1)

load_figure / figures.css.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-12T14:20:51+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · check_figure accepts literal colours via !important, modern colour functions, upper-case property names and SMIL (phase 1)

Probed by the reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-12T14:20:51+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · check_figure regex gaps: data-role accepted as role, > in a root attribute refused, SMIL href, @import, xml:id, prose refused as an event attribute (phase 1)

Probed by the reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-12T14:20:51+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · Test gaps: loose match words, no test of the narrow/wide switch or classless colour; fill_figures bypasses the tested load_figure (phase 1)

tests/unit/test_build_site.py.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-12T14:20:51+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · exit-gates page overclaims the driver's auto-pass of the tester gate; wave-driver page omits the --once --yes single-pass refusal (phase 1)

batch_drive.py:1713-1724; triage_batch_cmd.py:5218.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-11-12T14:20:51+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · wave-of-batches figures state 'at most 4 batches' in flight but 4 is only the --max-inflight default (phase 1)

scripts/site/figures/wave-of-batches*.svg.

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-11-12T14:20:51+00:00 phase=1 state=open review_scope=out -->
### p1-r8 · finding [open] (reviewer: out of scope) · At the spec's 600px breakpoint the 960-unit wide figure renders text near 7px at 601-800px (phase 1)

The reviewer tagged it out of scope because the breakpoint is the spec's.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-11-12T14:20:51+00:00 phase=1 -->
### p1-review · review · independent review of phase 1: 8 findings (phase 1)

Findings raised: p1-r1, p1-r2, p1-r3, p1-r4, p1-r5, p1-r6, p1-r7 (in scope), p1-r8 (out of scope). The reviewer ran the targeted tests (144 passed), ruff and fr docs check, probed check_figure with constructed inputs, and checked the two pages' claims against batch_drive.py, batch_merge.py, exit.py, gate_cmd.py and release.py. Fixes verified by the orchestrator at 08af58c8: check_figure parses XML with a paint allowlist; targeted tests green.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-12T14:20:51+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: fr-wave-driver.md says a draft is never merged, but an approved green draft is marked ready and merged (phase 1)

The page now says only an unapproved draft is held; an approved draft with green checks is marked ready and merged.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-12T14:20:51+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: A figure with no narrow file gets class fig-wide, which figures.css hides at narrow widths, so it vanishes on phones (phase 1)

The wide/narrow classes are added only when a narrow file exists; tested.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-12T14:20:51+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: check_figure accepts literal colours via !important, modern colour functions, upper-case property names and SMIL (phase 1)

check_figure parses the file as XML and applies an allowlist to paint values; SMIL elements are refused; a test per probed bypass.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-12T14:20:51+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: check_figure regex gaps: data-role accepted as role, > in a root attribute refused, SMIL href, @import, xml:id, prose refused as an event attribute (phase 1)

Element and attribute checks replace the regexes; @import and unprefixed xml:id are refused; the false refusals are tested as accepted.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-12T14:20:51+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: Test gaps: loose match words, no test of the narrow/wide switch or classless colour; fill_figures bypasses the tested load_figure (phase 1)

The defect test matches specific phrases; fill_figures calls load_figure; tests added for the page-naming refusal, the switch and the svg paint defaults.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-12T14:20:51+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: exit-gates page overclaims the driver's auto-pass of the tester gate; wave-driver page omits the --once --yes single-pass refusal (phase 1)

Both qualifiers added after checking batch_drive.py and triage_batch_cmd.py.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-11-12T14:20:51+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: wave-of-batches figures state 'at most 4 batches' in flight but 4 is only the --max-inflight default (phase 1)

Both figures now say 'up to the cap (default 4)'.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-11-12T14:20:51+00:00 phase=1 state=open resolves=p1-r8 out_of_scope=true -->
### p1-r8-resolved · finding [out-of-scope] · resolves p1-r8: At the spec's 600px breakpoint the 960-unit wide figure renders text near 7px at 601-800px (phase 1)

Not caused by the phase's code: the 600px breakpoint was the spec's. The spec was corrected to 860px in this run and figures.css follows it, so nothing is left to file.
