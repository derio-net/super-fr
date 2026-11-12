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
