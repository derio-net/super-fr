# Journal: 2026-09-29-requirements-precheck

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-09-29T11:09:05+00:00 -->
### repro-1 · repro · pre-check exits 2 on citations the pending brainstorm resolve writes; Deferred errors labelled ## Requirements

Take 10 runs A/B (#817): `fr spec requirements <spec>` run before `fr run resolve --step brainstorm --record` exits 2 with "source cites decision d-x, which is not a kind=decision entry" and "requirement R<n>: not cited by any matrix row" — both written by that same record. Only the input entry was treated as pending. Separately, a malformed row in `## Deferred from input` reports as "`## Requirements`: line N: ..." and no row-level error shows the `| "<quote>" | <reason> |` shape; run A deleted the section, B found the shape on its 3rd try.

<!-- fr:journal kind=root-cause scope=debug id=rc-1 created=2026-09-29T11:09:08+00:00 -->
### rc-1 · root-cause · check_requirements knows only one pending citation, and prefixes every parse error with ## Requirements

`fr.requirements.check_requirements(input_pending=True)` suspends only the input-entry checks; decision-id and matrix-citation checks read the on-disk journal/matrix, which the pending record has not yet staged (the resolve re-runs strictly on the staged state, so the resolve itself is right). And `check_requirements` wraps every RequirementsError as "`## Requirements`: {exc}" though `parse_requirements` also parses `## Deferred from input`; the row-level errors inside it name neither section nor row shape. Two defects in one member; the operator scoped both in the reopen comment, so they ship together.

<!-- fr:journal kind=finding scope=debug id=fix-1 created=2026-09-29T11:22:13+00:00 state=fixed -->
### fix-1 · finding [fixed] · pre-check lists the resolve's citations as pending; errors carry section + row shape

Source: `fr.requirements.check_requirements(pending=list)` replaces `input_pending`: an absent input entry, an absent decision id and an uncited requirement go to `pending` (printed by `fr spec requirements`, exit 0); a present non-decision id and a quote missing an existing input entry stay problems; the resolve passes no list, so it stays strict. `parse_requirements` wraps each section via `_in_section`, prefixing errors with the section and its row shape (`_ROW_SHAPES`). Tests failing first (commit on PR #827): test_pending_treats_a_decision_the_resolve_writes_as_pending, test_pending_treats_an_uncited_requirement_as_pending, test_deferred_row_error_names_its_section_and_row_shape, test_requirements_cmd_reports_what_the_resolve_writes_as_pending (+5). The old test_requirements_cmd_exits_2_on_an_unsound_spec pinned the defect (uncited → exit 2) and now uses a decision id naming a discovery. Full suite: 7574 passed. No artifact shape changed, so no current_version moves.

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-09-29T11:23:57+00:00 -->
### review-1 · review · independent review: one finding, fixed (double prefix in fidelity.py)

Independent read-only reviewer on the diff. Strict resolve path (pending=None): unchanged apart from message text. Classification pending vs problem: sound. One real finding: fr/fidelity.py check_fidelity/check_inventory re-prefixed parse_requirements errors with `## Requirements`, doubling the prefix and blaming the wrong section for a Deferred row — fixed (str(exc)), pinned by test_a_malformed_deferred_row_is_reported_once_under_its_own_section. Low-confidence edge noted, not acted on: when an older input entry exists and the record adds a second, quotes matching only the new one are problems in the pre-check (the pending stance is absence-only, by design).
