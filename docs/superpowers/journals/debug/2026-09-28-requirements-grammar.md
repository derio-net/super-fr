# Journal: 2026-09-28-requirements-grammar

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-28T19:00:47+00:00 -->
### repro · repro · Requirements gate refuses guessed source forms; its errors never name the valid ones

Probe against origin/main df7c7bb0 (`parse_requirements` + `quote_matches`, body containing `"basket"` and `"✓ 680–720 g"`):

- `input "labelled "✓ 680–720 g" when"` (unescaped inner quotes) -> parses, value `labelled "✓ 680–720 g" when`, MATCHES.
- `input "labelled \"✓ 680–720 g\" when"` (backslash-escaped) -> parses, value keeps the backslashes, NEVER matches.
- `“A basket is a list”` (curly quotes, no `input` keyword; take 9 of #776) -> `line 5: unknown source form ...`, with no word on what a valid form is.
- `fr spec requirements` before the brainstorm resolve that writes the input entry -> `no input entry (...) found in the spec journal` + every input quote reported as not matching.

<!-- fr:journal kind=ruled-out scope=debug id=quotes-cannot-contain-dquote created=2026-09-28T19:00:49+00:00 -->
### quotes-cannot-contain-dquote · ruled-out · Ruled out: "a quote cannot contain a double quote"

`_INPUT_SOURCE_RE` is `^input\s+"(.*)"$` (greedy, DOTALL): the quote runs first `"` to last `"`, so unescaped inner quotes already parse and match (probe above). The truncation in take 9 came from the agent not knowing that: it guessed an escape (`\"`, kept literally, never matches) or cut the quote short. The fault is that the grammar is undocumented, not that the parser rejects the character.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-09-28T19:00:51+00:00 -->
### root-cause · root-cause · The source-cell grammar exists only in fr/requirements.py

Every symptom in #776 is one cause: the `source` grammar (`input "<verbatim quote>"`, `decision <id>`, `<br>` between several) is stated nowhere an agent reads: not in fr-brainstorming §2 or fr-goal §1, and not in the gate error (`unknown source form` names none). So agents guess: curly quotes without the keyword, a `\"` escape the parser keeps literally, a quote cut at its first inner `"`. The pre-check wording is the same gap on the journal side: it calls "not written yet" missing, and it never says the resolve writes the entry.

<!-- fr:journal kind=finding scope=debug id=fix created=2026-09-28T19:23:08+00:00 state=fixed -->
### fix · finding [fixed] · Grammar documented where agents read it; errors and pre-check say what is valid and what is pending

Source: `fr/requirements.py` (`SOURCE_FORMS` in the unknown-form error with the row; `_unescape_quote` on input and Deferred quotes; `check_requirements(..., input_pending=)`), `fr/commands/spec_cmd.py` (pre-check passes `input_pending=True`, prints an `input entry: pending` line naming the resolve that writes it; the `fr run resolve` gate is unchanged and strict), fr-brainstorming §2 + fr-goal §1 (grammar, one example per form), both mirrors regenerated. Failing tests first (cfa008a6): `test_unknown_source_form_error_names_the_valid_forms_and_the_row`, `test_backslash_escaped_double_quote_is_unescaped`, `test_pending_input_entry_is_not_a_problem_before_resolve`, `test_input_pending_still_checks_quotes_once_the_entry_exists`, `test_requirements_cmd_reports_a_missing_input_entry_as_pending`; plus `test_the_skill_documented_grammar_example_parses` pinning the skill example to the parser, and `test_unescaped_double_quote_inside_a_quote_parses_and_matches` pinning the behaviour that already worked. Full suite: 6867 passed, 115 skipped.
