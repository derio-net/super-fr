# Journal: 2026-09-28-coverage-as-written

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-28T19:05:25+00:00 -->
### repro · repro · fr refuses the reviewer's raw input-coverage block; the orchestrator re-cut it to pass

Take 9 (fr 4.29.2, OpenCode; input content is a third-party brief, redacted here). The spec reviewer returned its input-coverage block one input line per span, with blank `""` spans and one `missing s1`. Replayed through `check_coverage` against the recorded input entry: `input-coverage table: line 47: expected 2 columns, got 6`. The orchestrator then read requirements.py and recorded a re-cut block (lines merged into paragraphs, blank spans dropped, `\"` unescaped, `|` escaped as `\|`, `missing s1` relabelled R11), which passes: the recorded evidence is not the reviewer's.

<!-- fr:journal kind=ruled-out scope=debug id=h-shape created=2026-09-28T19:05:43+00:00 -->
### h-shape · ruled-out · Blank spans, one-span-per-line and missing labels are not what fr refused

Replaying the raw block with only its pipes escaped and `\"` decoded passes check_coverage (94 spans, missing=1). fr already accepts `""` spans, line-granular spans and `missing <id>`; the paragraph merge and relabelling were never required.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-09-28T19:05:45+00:00 -->
### root-cause · root-cause · fr's span-cell decoder does not read a quoted span the way the reviewer writes one

check_coverage splits each row on every unescaped `|`, ignoring the `"…"` around the span, so a span quoting a Markdown table row (`| a | b |`) becomes 6 columns and the whole table is refused. And `\"` inside a span is kept literally, so the concatenation never equals the input. Both are encodings the reviewer brief never forbids (it says "quote it exactly"). With no readable shape and a refusal that names no remedy, the orchestrator's only path to a green gate was to edit the reviewer's block.

<!-- fr:journal kind=finding scope=debug id=fix created=2026-09-28T19:19:29+00:00 state=fixed -->
### fix · finding [fixed] · Coverage spans are read as the reviewer writes them; refusals route to the reviewer

requirements.py §D: `_protect_span_pipes` keeps a quoted span's raw `|` in one cell; `_coverage_form` reads `\"`/`\|` as `"`/`|` on both sides of the comparison (so no escape can hide a gap); an unquoted span is a reported problem, not an uncaught raise; table/label/partition refusals end with "re-dispatch the reviewer … never edit its partition". Pinned red-first by tests/unit/test_requirements.py::test_777_* (synthetic input in take 9's shape). Replaying take 9's untouched reviewer block now passes: 94 spans, missing=1. Reviewer brief and fr-goal SKILL updated; both mirrors resynced.
