# Journal: 2026-09-28-requirements-grammar

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-28T19:00:47+00:00 -->
### repro · repro · Requirements gate refuses guessed source forms; its errors never name the valid ones

Probe against origin/main df7c7bb0 (`parse_requirements` + `quote_matches`, body containing `"basket"` and `"✓ 680–720 g"`):

- `input "labelled "✓ 680–720 g" when"` (unescaped inner quotes) -> parses, value `labelled "✓ 680–720 g" when`, MATCHES.
- `input "labelled \"✓ 680–720 g\" when"` (backslash-escaped) -> parses, value keeps the backslashes, NEVER matches.
- `“A basket is a list”` (curly quotes, no `input` keyword; take 9 of #776) -> `line 5: unknown source form ...`, with no word on what a valid form is.
- `fr spec requirements` before the brainstorm resolve that writes the input entry -> `no input entry (...) found in the spec journal` + every input quote reported as not matching.
