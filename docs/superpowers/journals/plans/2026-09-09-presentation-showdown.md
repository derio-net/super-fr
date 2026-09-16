# Journal: 2026-09-09-presentation-showdown

<!-- fr:journal kind=decision scope=plan id=08da34f8334b created=2026-09-09T16:32:29 -->
### 08da34f8334b · decision · Protocol plan with demo-ticket placeholders

4 phases: manual env prep (P1), protocol+instrumentation (P2), dual runs+comparison (P3), Marp deck (P4). Seed prompt and acceptance checklist marked pending operator brief (ticket redacted) during repo prep.

<!-- fr:journal kind=decision scope=plan id=80269b644688 created=2026-09-09T16:34:59 -->
### 80269b644688 · decision · Instrument: runbook + half-1 deck skeleton

experiment/runbook.md (metrics, correction schema, recording runbook; demo-ticket placeholders pending). docs/presentation/super-fr-showdown.md skeleton: half 1 full, half 2 pending recordings, neutral comparison table.

<!-- fr:journal kind=decision scope=plan id=ca0284dfab55 created=2026-09-09T17:00:40 -->
### ca0284dfab55 · decision · Half-1 deck finished ahead of experiment

docs/presentation/super-fr-showdown.md: half 1 complete (12 slides), half 2 preview + empty table. Run stays parked at record-compare pending operator prep.

<!-- fr:journal kind=decision scope=plan id=ab5350f56abb created=2026-09-11T10:04:08 -->
### ab5350f56abb · decision · Half-2 ending left open: comparison vs annotation playback

Operator: likely no time for full comparison. Options: pruned comparison table or annotated session playback. Decision deferred; deck closes open-ended.

<!-- fr:journal kind=decision scope=plan id=7ffa5836d40e created=2026-09-11T10:40:09 -->
### 7ffa5836d40e · decision · Deck rebuilt to factory map: 25 slides, 16 portrait prompts

Stages with ASCII flows, stats+#449, 11 upgrade slides with halo-portrait placeholders, crib+testtrack close, ending open (comparison vs playback). Portrait PNGs pending operator generation.

<!-- fr:journal kind=decision scope=plan id=034fab6daa04 created=2026-09-11T10:42:46 -->
### 034fab6daa04 · decision · Ending locked: annotated fr-goal playback, no full comparison

1h slot. Half 2 = one annotated fr-goal run narrated live. Comparison table dropped.

<!-- fr:journal kind=decision scope=plan id=460b1d3a04a7 created=2026-09-11T18:47:45 -->
### 460b1d3a04a7 · decision · Migrated deck to reveal.js for nonlinear detours

23 horizontal, 12 upgrades carry vertical D-slides with back-links. Marp source retained until reveal verified slide-for-slide. Navigation: Esc overview, S speaker view, hash links.

<!-- fr:journal kind=finding scope=plan id=6d0f93c31412 created=2026-09-16T09:02:02 state=fixed -->
### 6d0f93c31412 · finding [fixed] · data-markdown slides silently dropped all raw HTML

reveal's markdown plugin reads `section.textContent` for inline `data-markdown` slides, so every raw HTML child is reduced to its text. Commit 3f6974b added `data-markdown` around existing markup, which at render time destroyed: 3 crumbs, 2 side portraits, 15 detour back-links (all dead), the `split`/`title`/`divider` slide classes (set via `<!-- .slide: -->` comments, which have no textContent), and 20 speaker notes. The deck still rendered, so nothing looked wrong. Two notes (slides 'What is this talk really about', 'Agenda') were additionally deleted outright by that commit. Fix: wrap every data-markdown body in `<script type="text/template">` (reveal's supported inline form — its textContent is the literal source, so raw HTML survives), convert raw `<aside class="notes">` to reveal's `Note:` separator, flatten a stray wrapper section that orphaned the 'Feature velocity' crumb, restore `class="chain"` on the converted ASCII flow, and restore the 2 deleted notes from c572ec3. Verified by rendering the pre-conversion baseline (c572ec3) and the fixed deck and comparing: 37 leaf slides, 18 crumbs, 0 orphaned, 17 side images, 0 broken, 28 nav links all resolving, 23 non-empty notes, 3 chain blocks, 20 classed slides, identical heading list.

<!-- fr:journal kind=decision scope=plan id=cec37cdd8541 created=2026-09-16T09:53:17 -->
### cec37cdd8541 · decision · Deck prose externalized to slides.md, index.html generated

slides.md is now the source of truth for all 37 slides; `build.py` inlines it into index.html as `<script type="text/template">` blocks (+ template.html for the shell). Chose generation over reveal's external-markdown mode deliberately: external markdown is fetched by XMLHttpRequest, which browsers block under file://, so it would have cost the deck's double-click/offline property. Generating keeps index.html self-contained. Guards: `tests/unit/test_tripwire_deck_fresh.py` (6 tests) fails if index.html is stale, pins the script-template wrapper, and pins that separators inside fenced code do not split slides; `build.py` itself refuses a slide whose `Note:` is not last. That last guard came from a real bug found during the conversion: reveal's notes separator is greedy, so the 15 slides carrying `<img class=\"side\">` after their `<aside>` had the portrait swallowed into the speaker note, where it rendered inside a collapsed `<p>` and `img.side { width: 34% }` resolved to 34% of zero. Verified by fingerprinting the pre-externalization deck and the generated one in a browser and diffing per slide on index, class, background, visible text, note text, side images, images-trapped-in-notes, links and pre classes: 0 diffs across 37 slides, plus all 17 split slides confirmed to have a correctly-sized non-overlapping portrait.

<!-- fr:journal kind=finding scope=plan id=f405276727e8 created=2026-09-16T10:31:20 state=fixed -->
### f405276727e8 · finding [fixed] · Title slide re-laid-out on resize: vh units escape reveal's scaling

Reveal lays slides out on a fixed 960x700 logical canvas scaled by a CSS transform. Lengths in px/em/% live inside that scaled system; `vh`/`vw` are measured against the real window and so do not scale with it. The theme used `vh` in three places, all on the title slide (`padding-top: 6vh` twice, `.topblock { padding: 0 0 3vh }`) plus `img.side { max-height: 76vh }`. Measured drift on the title slide's h1, in logical px: 54 at 1600x900, 37 at 1100x620, while a control split slide held at 88 across both. Fixed by converting to the logical px the `vh` resolved to at fullscreen 1920x1080 (6vh -> 44, 3vh -> 22, 76vh -> 555), preserving the presentation-size appearance to within 0.2px. Verified at four real viewport sizes (1920x1080, 1280x800, 1100x620, 900x1200): title h1 = 44 and h2 = 145 at every one, split controls unchanged. Guard: `test_the_theme_uses_no_viewport_units`, which strips comments first so the explanatory note may still name the units. Note for future measurement work: an in-page resize emulation that sets documentElement width/height cannot detect this class of bug at all, because `vh` tracks the real viewport, which such an emulation never changes.

<!-- fr:journal kind=finding scope=plan id=cea6c61cdeab created=2026-09-16T13:28:07 state=fixed -->
### cea6c61cdeab · finding [fixed] · Title background cropped to 48% on non-16:9 windows

factory-line.png is 1672x941 (aspect 1.777, i.e. 16:9) and the title slide set `data-background-size="cover"`. On a 16:9 screen cover fills exactly, but on anything narrower it scales to the height and crops the sides: 90% of the image width survives at 16:10, and only 47.7% at the operator's portrait 1627x1920 window — cutting off the left-hand station that the slide's left-to-right reading (and its speaker note) depends on. Fixed with `@media (max-aspect-ratio: 16/9)` switching that one background to `contain`. Because the image is itself 16:9, contain and cover agree exactly at 16:9, so there is no visual jump at the switch and the presentation case is byte-for-byte unchanged (verified: 100% x 100% visible at 1920x1080 under both). Selector is `.slide-background.title .slide-background-content` — reveal copies the slide's own class onto its background element, so this needs no :nth-child index coupling; `!important` is required because reveal writes the size as an inline style. Verified at four aspects: 2.37 ultrawide -> cover (unchanged), 1.778 -> contain 100%, 1.60 -> contain 100% (was 90%), 0.85 portrait -> contain 100% (was 47.7%), confirmed visually by screenshot showing all three station plates 1/2/3 where previously only 2 was visible.
