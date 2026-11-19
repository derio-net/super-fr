<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-batch-docs-wording

<!-- fr:journal kind=discovery scope=plan id=p1-bracket-set created=2026-11-19T11:24:46+00:00 phase=1 -->
### p1-bracket-set · discovery · R5's test flagged more strings than the spec listed (phase 1)

Besides init scaffold --tool, acceptance_cmd.py:755,1137,1141 and triage_batch_cmd.py:773, `fr plan create`'s docstring (`[row-ids]`, `[globs]`) lost its brackets too; all escaped.

<!-- fr:journal kind=discovery scope=plan id=p1-ste-first-sentence created=2026-11-19T11:24:46+00:00 phase=1 -->
### p1-ste-first-sentence · discovery · cli.md STE FAILs came from 13 help first sentences (phase 1)

The tree carries only the first sentence (sync-readme.first_sentence), so each fix split the docstring's opening into a short first sentence and kept the remaining facts as following sentences; the pinned checker reports no FAIL.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-19T11:24:46+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the R1 hint text appears in one message only; nothing to share

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-19T11:24:46+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

prose-only edits; the new test file is already minimal

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-11-19T11:33:06+00:00 phase=1 -->
### p1-review · review · Phase 1 review (R1-R10): no findings (phase 1)

A separate reviewer checked R1-R10 against the code: the ops gate hint
(ops_gate_cmd.py:206-208), seal's target (helpers.py:164 shlex.quote),
the rework help (plan_ops.rework_create), the rich-safe escapes and the
bracket test (it walks every command and param help, and has a failing and
a passing self-test), cli.md STE (no exemption, two exceptions pinned),
the skill prose against is_debt/open_rows, the triage schema pin, the
mirrors and the acceptance refs. Minor blind spots in the bracket test
(epilog, short_help, substring masking) are noted but none apply today.
The reviewer had no shell, so the orchestrator ran the checks: the sync
--check runs, fr docs check, fr acceptance check, the STE checker (0
FAIL) and the targeted tests, all green after merging origin/main.
review-findings: none

<!-- fr:journal kind=discovery scope=plan id=p2-fence-in-list-not-read created=2026-11-19T13:47:20+00:00 phase=2 -->
### p2-fence-in-list-not-read · discovery · A fence inside a list item never renders under the pinned renderer, at any indent (phase 2)

The spec (R11) assumed a 4-space indent makes Python-Markdown read a fence inside a list
item. Checked with markdown 3.11 and the pinned blog-craft renderer: fenced_code matches only
a fence at the start of a line, so 2, 3 and 4 spaces all give inline code. What renders as a
block inside a list item is an indented code block (8 spaces, blank line around it).
So the four pages now carry indented code blocks (no fence, no language), and the R12
refusal message says to write the code as an 8-space block or move it out of the list.
Spec R11's "4 spaces" wording is stale; the observable R11 outcome (code blocks inside
their list items) holds.

<!-- fr:journal kind=discovery scope=plan id=p2-mermaid-fence created=2026-11-19T13:47:20+00:00 phase=2 -->
### p2-mermaid-fence · discovery · The R12 check skips mermaid fences (phase 2)

docs/explainers/fr-isolation.md holds a mermaid fence, which the renderer stashes and
re-inserts as <pre class="mermaid"> with its own text, so its body never matches a <pre> of
the markdown render. source_fences skips an info word starting with mermaid.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-19T13:47:20+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

whitespace-only page edits and a rule sentence; no code to clean

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-19T13:54:38+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · docs-currency.md examples lost one space of relative indent (phase 2)

The YAML example stepped by 1 space and the bash continuation by 1, where the original used 2; R11 says the examples' text does not change.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-19T13:54:38+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · R12 passes a fence rendered as literal text in a <pre> (phase 2)

A fence indented as an indented code block renders with its fence lines as text inside a <pre>; the body match passed it.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-19T13:54:38+00:00 phase=2 state=open review_scope=out -->
### p2-r3 · finding [open] (reviewer: out of scope) · _FENCE captures only three backticks or tildes (phase 2)

Four-backtick nesting mispairs in source_fences and fill_figures alike; predates this change, no tracked page uses it.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-19T13:54:38+00:00 phase=2 state=open review_scope=out -->
### p2-r4 · finding [open] (reviewer: out of scope) · source_fences skips every mermaid fence (phase 2)

A mermaid fence inside a list item is never checked; the renderer owns mermaid placement and no page does this today.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-19T13:54:38+00:00 phase=2 state=open review_scope=out -->
### p2-r5 · finding [open] (reviewer: out of scope) · spec R12 design described counting, the code matches by body (phase 2)

Behaviour correct; spec wording loose.

<!-- fr:journal kind=finding scope=plan id=p2b-r1 created=2026-11-19T13:54:38+00:00 phase=2 state=open review_scope=in -->
### p2b-r1 · finding [open] (reviewer: in scope) · R12 body match by substring lets a longer unrelated <pre> satisfy a short fence (phase 2)

want in pre accepted any <pre> containing the body.

<!-- fr:journal kind=finding scope=plan id=p2b-r2 created=2026-11-19T13:54:38+00:00 phase=2 state=open review_scope=out -->
### p2b-r2 · finding [open] (reviewer: out of scope) · an unclosed fence is never recorded by source_fences (phase 2)

An unclosed fence swallows the rest of the page in the renderer too; no page has one.

<!-- fr:journal kind=finding scope=plan id=p2b-r3 created=2026-11-19T13:54:38+00:00 phase=2 state=open review_scope=out -->
### p2b-r3 · finding [open] (reviewer: out of scope) · a fence inside an HTML comment or an indented fence example is still recorded (phase 2)

Could refuse falsely; no current page affected, and a refusal is the safe direction.

<!-- fr:journal kind=review scope=plan id=p2-review created=2026-11-19T13:54:38+00:00 phase=2 -->
### p2-review · review · Phase 2 review (R11-R13): two reviews, three in-scope findings, all fixed (phase 2)

A separate reviewer built the real site with the pinned renderer (32 pages; the four
examples in <pre> inside their lists; the docs-currency site list items 1-6; the
landing lists still filled), ran test_build_site.py, sync-opencode --check, fr docs
check and fr acceptance check. p2-r1 and p2-r2 fixed in f2dc84758 (re-indent; a <pre>
that also shows the fence's opening line no longer counts, new test
test_a_fence_rendered_as_literal_text_in_a_pre_is_refused); p2-r5's spec wording
also corrected there. Rebuilt site: the examples' rendered text matches the originals.
A second reviewer, dispatched after the review step opened, re-checked the whole
phase including those fixes (site build, test_build_site.py, sync, docs, acceptance,
STE: all clean) and raised p2b-r1, fixed in 07144bc84 (whole-block match; new test
test_a_short_fence_body_is_not_satisfied_by_a_longer_pre); the real build still passes.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-19T13:54:38+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: docs-currency.md examples lost one space of relative indent (phase 2)

f2dc84758: the two examples keep their original relative indent (rendered text checked against the original).

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-19T13:54:38+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: R12 passes a fence rendered as literal text in a <pre> (phase 2)

f2dc84758: check_fences_render refuses when the only matching <pre> also shows the fence's opening line; pinned by a new test.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-19T13:54:38+00:00 phase=2 state=open resolves=p2-r3 out_of_scope=true -->
### p2-r3-resolved · finding [out-of-scope] · resolves p2-r3: _FENCE captures only three backticks or tildes (phase 2)

_FENCE's three-character capture predates this change and no page nests fences.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-19T13:54:38+00:00 phase=2 state=open resolves=p2-r4 out_of_scope=true -->
### p2-r4-resolved · finding [out-of-scope] · resolves p2-r4: source_fences skips every mermaid fence (phase 2)

The mermaid skip mirrors the renderer, which rewrites mermaid fences itself; a mermaid fence in a list item is a renderer concern no page has.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-19T13:54:38+00:00 phase=2 state=open resolves=p2-r5 out_of_scope=true -->
### p2-r5-resolved · finding [out-of-scope] · resolves p2-r5: spec R12 design described counting, the code matches by body (phase 2)

Not a defect in the change's behaviour; the spec's R12 design wording was nonetheless corrected in f2dc84758.

<!-- fr:journal kind=finding scope=plan id=p2b-r1-resolved created=2026-11-19T13:54:38+00:00 phase=2 state=fixed resolves=p2b-r1 -->
### p2b-r1-resolved · finding [fixed] · resolves p2b-r1: R12 body match by substring lets a longer unrelated <pre> satisfy a short fence (phase 2)

07144bc84: a fence's body must be the whole (whitespace-normalised) text of a <pre>; pinned by a new test, the 32-page build still passes.

<!-- fr:journal kind=finding scope=plan id=p2b-r2-resolved created=2026-11-19T13:54:38+00:00 phase=2 state=open resolves=p2b-r2 out_of_scope=true -->
### p2b-r2-resolved · finding [out-of-scope] · resolves p2b-r2: an unclosed fence is never recorded by source_fences (phase 2)

Predates this change; an unclosed fence breaks the renderer's page as a whole, and no page has one.

<!-- fr:journal kind=finding scope=plan id=p2b-r3-resolved created=2026-11-19T13:54:38+00:00 phase=2 state=open resolves=p2b-r3 out_of_scope=true -->
### p2b-r3-resolved · finding [out-of-scope] · resolves p2b-r3: a fence inside an HTML comment or an indented fence example is still recorded (phase 2)

Source scanning is line-based by design; no page has a fence in a comment or an indented fence example.

<!-- fr:journal kind=decision scope=plan id=p3-article-bar-follows-column created=2026-11-19T14:46:28+00:00 phase=3 -->
### p3-article-bar-follows-column · decision · The article bar's padding follows the 720px column, not only the phone gutter (phase 3)

Screenshots at 1280 px showed the article bar's text at x=21 while the h1 sat at x=280
(the bar is pulled out to the viewport edge; the column is 720px centred). R15 names
desktop widths, so bar.css's padding is now max(1.25rem, (100% - 720px)/2 + 1.25rem);
the added 1.25rem is because a padding percentage resolves against the body's content
box, 2.5rem narrower than the bar. Measured: name text and h1 both at 280 at 1280,
both at 21.3 at 320 and 390. Landing: both at 18.4 (320, 390), 105.5 (1280).

<!-- fr:journal kind=discovery scope=plan id=p3-link-tap-height created=2026-11-19T14:46:28+00:00 phase=3 -->
### p3-link-tap-height · discovery · Bar links were 17px tall on a phone; a 0.35rem vertical padding gives about 29px (phase 3)

The vertical padding applies to the four links only (a:not(.site-name)) inside the
480px rule, so the name row keeps its height. Link boxes at 320: x 21-96 / 111-156 /
171-239 / 253-299, none overlapping, all in one row (top 46.1).

<!-- fr:journal kind=finding scope=plan id=p3-article-table-overflow created=2026-11-19T14:46:28+00:00 phase=3 state=open review_scope=out -->
### p3-article-table-overflow · finding [open] (reviewer: out of scope) · 01-fr-goal.html scrolls horizontally on a phone because of a wide table, not the bar (phase 3)

document.documentElement.scrollWidth is 597 at 320 and 390 on 01-fr-goal.html; the
offender is a TABLE in the article (right edge 597). The bar itself is exactly the
viewport wide (scrollWidth == clientWidth). fr-audit, a guide and a reference page
measure scrollWidth == innerWidth at 320/390. The table is article content from the
renderer, outside R14's bar scope; not fixed here.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-19T14:46:28+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

CSS and a measuring script only; the code of T1 had nothing left to tidy beyond its own S3

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-19T14:50:17+00:00 phase=3 state=open review_scope=out -->
### p3-r1 · finding [open] (reviewer: out of scope) · guides/ops.html and reference/install.html scroll horizontally at 320px from wide code blocks (phase 3)

scrollWidth 379 and 376 at 320 px; the bar's own scrollWidth is 320. Wide yaml/bash code blocks, not the bar.

<!-- fr:journal kind=review scope=plan id=p3-review created=2026-11-19T14:50:17+00:00 phase=3 -->
### p3-review · review · Phase 3 review (R14-R15): no in-scope findings (phase 3)

A separate reviewer built the site, captured its own screenshots with its own script
(headless Chromium 1243, file:// URLs) and measured with JS: at 320/390 the site name
is alone on row 1 and the four links share row 2 with no overlap (links 29.5px tall,
27.8 on the landing); bar scrollWidth == clientWidth; fr-audit.html and index.html
scrollWidth == innerWidth at 320/390/1280; bar text left edge == h1 left edge (21.25
article/guide/reference, 18.4 landing at phone widths; 280 and 105.5 at 1280). The
padding max() resolves against the viewport (bar bleeds to full width). Light and dark
give identical geometry. The 480px-rule and padding tests would fail without the rules.
fr docs check and fr acceptance check clean. Only finding: p3-r1 (out of scope).

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-19T14:50:17+00:00 phase=3 state=open resolves=p3-r1 out_of_scope=true -->
### p3-r1-resolved · finding [out-of-scope] · resolves p3-r1: guides/ops.html and reference/install.html scroll horizontally at 320px from wide code blocks (phase 3)

The page overflow comes from wide code blocks in the page body, which this change does not touch; R14 is about the bar, whose own width fits at 320 px.

<!-- fr:journal kind=finding scope=plan id=p3-article-table-overflow-resolved created=2026-11-19T14:50:17+00:00 phase=3 state=open resolves=p3-article-table-overflow out_of_scope=true -->
### p3-article-table-overflow-resolved · finding [out-of-scope] · resolves p3-article-table-overflow: 01-fr-goal.html scrolls horizontally on a phone because of a wide table, not the bar (phase 3)

01-fr-goal.html overflows on phones from a wide article table in its body, not the bar; this change does not touch article content or table styling.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-19T14:57:45+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · R12 fence tests used only a stand-in renderer

The stand-in encoded the same rule as the check, so real Python-Markdown behaviour was never tested.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-19T14:57:45+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · check_fences_render let one <pre> satisfy two fences with one body

Matching was by membership, not per occurrence.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-19T14:57:45+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · bracket-help test matched spans by presence against the whole page

A duplicated span, or one also in the usage line, masked an eaten copy.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-19T14:57:45+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · R14/R15 tests pin CSS strings rather than measuring layout

They would pass with a visually wrong bar.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-19T14:57:45+00:00 state=open review_scope=in -->
### l-tests-r5 · finding [open] (reviewer: in scope) · ops/rework help tests asserted trivially-true substrings

'path', 'live', 'archived' occur elsewhere in the help.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6 created=2026-11-19T14:57:45+00:00 state=open review_scope=in -->
### l-tests-r6 · finding [open] (reviewer: in scope) · acceptance-skill prose test was negative-only

It never asserted the corrected claim.

<!-- fr:journal kind=finding scope=plan id=l-tests-r7 created=2026-11-19T14:57:45+00:00 state=open review_scope=in -->
### l-tests-r7 · finding [open] (reviewer: in scope) · fill_pages filled an own-line marker inside a fenced block

A page showing the marker in a fence would get the list spliced in; untested, as was trailing text.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-19T14:57:45+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · cli.md reviewed stamp repeated older notes and missed this batch

The merge resolution concatenated two overlapping stamps.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-19T14:57:45+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · docs-currency.md did not say the marker fills only on its own line

Item 5 of 'How this repo builds its site' was incomplete.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-19T14:57:45+00:00 -->
### lens-review-1 · review · Lens review: tests (7 findings) and docs-accuracy (2 findings)

One reviewer per lens over the whole diff from merge base f1b70d979. tests examined the
five test files, build-site.py, bar.css and landing.css; docs-accuracy examined cli.md,
docs-currency.md, the explainers-currency rule, fr-devops-gate/fr-acceptance/fr-exit-gates
pages, build-site.py, the site CSS, ops_gate_cmd.py and three skills. Fixes: 6f09a0ec2
(docs-accuracy r1, r2), 61b658f7b (tests r1, r2, r3, r5, r6, r7), 4daf69e36 (markdown in
the dev group so r1's real-converter tests run in CI). l-tests-r4 refuted.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-19T14:57:45+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: R12 fence tests used only a stand-in renderer

61b658f7b + 4daf69e36: tests run the real Python-Markdown converter with the renderer's extensions (2/3/4-space list fences refused, top-level fence and 8-space block pass); markdown is a dev dependency so CI runs them.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-19T14:57:45+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: check_fences_render let one <pre> satisfy two fences with one body

61b658f7b: each fence consumes one <pre> (Counter); test_two_fences_with_one_body_each_need_their_own_pre fails on the old code.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-19T14:57:45+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: bracket-help test matched spans by presence against the whole page

61b658f7b: missing_spans is count-based per page; new self-tests for a duplicated span with one copy eaten and a span also in the usage line.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-19T14:57:45+00:00 state=refuted resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [refuted] · resolves l-tests-r4: R14/R15 tests pin CSS strings rather than measuring layout

The layout itself is proven by the row's visual evidence: two reviewers' own screenshots and JS measurements at 320/390/1280 recorded at review-phase phase/3. CI has no browser, so the unit tests deliberately guard the rules that produce that layout against regression; a layout test would need browser infrastructure this repo's suite does not have.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-19T14:57:45+00:00 state=fixed resolves=l-tests-r5 -->
### l-tests-r5-resolved · finding [fixed] · resolves l-tests-r5: ops/rework help tests asserted trivially-true substrings

61b658f7b: the tests assert the replacement sentences (whitespace-normalised) for seal's {target} and the rework parent.

<!-- fr:journal kind=finding scope=plan id=l-tests-r6-resolved created=2026-11-19T14:57:45+00:00 state=fixed resolves=l-tests-r6 -->
### l-tests-r6-resolved · finding [fixed] · resolves l-tests-r6: acceptance-skill prose test was negative-only

61b658f7b: the test also asserts the corrected sentence (listed only while it is debt).

<!-- fr:journal kind=finding scope=plan id=l-tests-r7-resolved created=2026-11-19T14:57:45+00:00 state=fixed resolves=l-tests-r7 -->
### l-tests-r7-resolved · finding [fixed] · resolves l-tests-r7: fill_pages filled an own-line marker inside a fenced block

61b658f7b: fill_pages skips fenced lines; test_a_marker_shown_in_a_fence_or_followed_by_text_is_left_as_written fails on the old code. Docs and rule say so.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-19T14:57:45+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: cli.md reviewed stamp repeated older notes and missed this batch

6f09a0ec2: one stamp, this batch's note first, then main's.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-19T14:57:45+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: docs-currency.md did not say the marker fills only on its own line

6f09a0ec2 and 61b658f7b: item 5 says the marker fills only alone on its line, outside a fenced block.
