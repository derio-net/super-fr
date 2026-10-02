# Journal: 2026-10-02-acceptance-integrity

<!-- fr:journal kind=repro scope=debug id=7450e8a5efc5 created=2026-10-02T17:38:25+00:00 -->
### 7450e8a5efc5 · repro · #470: insert_row emits an invalid matrix when rows are flush-left

Reproduced in-process: a matrix whose `rows:` items are flush-left (`- id:`, PyYAML's default dump) fails `yaml.safe_load` after `fr.acceptance.edit.insert_row` — on BOTH paths (same-capability insert and new-capability append). `render_row_block` unconditionally prefixes every line with two spaces, so the new item is indented deeper than its siblings and parses as a continuation of the previous row's mapping.
