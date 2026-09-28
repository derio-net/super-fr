# Journal: 2026-09-28-requirements-traceability

<!-- fr:journal kind=decision scope=plan id=plan-approach-a created=2026-09-28T07:14:10+00:00 -->
### plan-approach-a · decision · Four layered phases (parser skeleton, artifact shapes, run gates, prose)

Operator-approved in the standalone fr-plan dialogue before switching to fr-goal. Chosen over vertical per-requirement slices (reopens run_cmd/pr_body/record model 3-4 times) and two phases (a ~2100-line phase 1).

<!-- fr:journal kind=discovery scope=plan id=req-coverage-span-join created=2026-09-28T08:57:17+00:00 phase=1 -->
### req-coverage-span-join · discovery · check_coverage's span reconstruction was joining with "", not a single space (phase 1)

§D says the partition check should "compare with single-space joins on
both sides so span boundaries carry no whitespace ambiguity" — both the
input entries (already joined with `" "` across journal entries) and
the spans (joined across coverage-table rows). The inherited draft
joined spans with `"".join(spans)`. Fixed to `" ".join(spans)` in
`fr.requirements.check_coverage`; `normalise` collapses the resulting
doubled whitespace at any boundary that already had its own, so every
existing test (including the #759 replay, whose spans meet at a real
whitespace boundary) still passes either way — the fix only matters for
a partition whose span boundary has no natural whitespace, which none
of the current fixtures exercise but a reviewer-authored one could.

<!-- fr:journal kind=discovery scope=plan id=req-cli-pretoken-bridge created=2026-09-28T08:57:17+00:00 phase=1 -->
### req-cli-pretoken-bridge · discovery · fr spec requirements's CLI test bridges the pre-token input-entry convention (phase 1)

`fr.requirements.is_input_entry` reads the `input` attribute via
`getattr` (per this phase's brief); phase 2 adds the real
`JournalEntry.input` field (spec §A). Until then, a `parse_journal`
-produced entry can never carry `.input` — `parse_journal` projects only
named header fields onto the model (extra="forbid"), so writing an
unrecognized `input=true` token to a real journal file today is
silently dropped, same as any other unknown token.

T1.S1's walking-skeleton CLI test needs `check_requirements`'s "at
least one input entry" check (§C.1) to actually pass against a real,
on-disk spec journal. `tests/unit/test_spec_requirements_cmd.py`
resolves this with a test-local bridge: it writes a `kind=discovery`
entry whose id starts `input-` (the pre-token naming convention this
note documents) and monkeypatches `spec_cmd.parse_journal` to wrap any
such entry in a small stand-in exposing `.input = True` before handing
it to `check_requirements` — the same idiom `test_requirements.py`'s
`_input_entry` helper already uses for its pure-function tests, just
also applied around the CLI's real file-reading path so that path gets
exercised today instead of waiting for phase 2.

Nothing in production code (`fr.requirements`, `spec_cmd.py`) knows
about the `input-` id prefix; the bridge lives entirely in the test
file. Phase 2 (P2.T1.S2, "Switch requirements.is_input_entry's test
helper to the real token") should remove this test-local bridge in the
same motion it switches `test_requirements.py`'s helper, once
`fr journal add --input` can write a real, recognized entry — flagging
it here so that step doesn't miss the second call site.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-28T08:57:17+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

The walking skeleton is a thin CLI wrapper (requirements_cmd) delegating to parse_requirements/check_requirements; there is nothing in it to extract. The shared parsing helpers it and every other task lean on (_split_row, _locate_section, _parse_table) are T2's refactor step.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-28T08:57:17+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

check_requirements's two local closures (_cited, _quote_ok) are already single-purpose and used once each; the decision/input source-kind branching is a two-armed dispatch with no duplication across it to pull out.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-09-28T08:57:17+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

check_coverage already reuses T2's shared _parse_table/_split_row for its own input-coverage block (the refactor step's own stated purpose, "used by both tables (and later by check_coverage's block)"); the label classification is one linear scan over four mutually exclusive forms, nothing repeated to extract.
