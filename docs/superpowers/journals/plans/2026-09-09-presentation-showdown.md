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
