# Journal: 2026-09-28-coverage-as-written

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-28T19:05:25+00:00 -->
### repro · repro · fr refuses the reviewer's raw input-coverage block; the orchestrator re-cut it to pass

Take 9 (fr 4.29.2, OpenCode; input content is a third-party brief, redacted here). The spec reviewer returned its input-coverage block one input line per span, with blank `""` spans and one `missing s1`. Replayed through `check_coverage` against the recorded input entry: `input-coverage table: line 47: expected 2 columns, got 6`. The orchestrator then read requirements.py and recorded a re-cut block (lines merged into paragraphs, blank spans dropped, `\"` unescaped, `|` escaped as `\|`, `missing s1` relabelled R11), which passes: the recorded evidence is not the reviewer's.
