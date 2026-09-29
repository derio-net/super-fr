# Journal: 2026-09-29-requirements-precheck

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-09-29T11:09:05+00:00 -->
### repro-1 · repro · pre-check exits 2 on citations the pending brainstorm resolve writes; Deferred errors labelled ## Requirements

Take 10 runs A/B (#817): `fr spec requirements <spec>` run before `fr run resolve --step brainstorm --record` exits 2 with "source cites decision d-x, which is not a kind=decision entry" and "requirement R<n>: not cited by any matrix row" — both written by that same record. Only the input entry was treated as pending. Separately, a malformed row in `## Deferred from input` reports as "`## Requirements`: line N: ..." and no row-level error shows the `| "<quote>" | <reason> |` shape; run A deleted the section, B found the shape on its 3rd try.

<!-- fr:journal kind=root-cause scope=debug id=rc-1 created=2026-09-29T11:09:08+00:00 -->
### rc-1 · root-cause · check_requirements knows only one pending citation, and prefixes every parse error with ## Requirements

`fr.requirements.check_requirements(input_pending=True)` suspends only the input-entry checks; decision-id and matrix-citation checks read the on-disk journal/matrix, which the pending record has not yet staged (the resolve re-runs strictly on the staged state, so the resolve itself is right). And `check_requirements` wraps every RequirementsError as "`## Requirements`: {exc}" though `parse_requirements` also parses `## Deferred from input`; the row-level errors inside it name neither section nor row shape. Two defects in one member; the operator scoped both in the reopen comment, so they ship together.
