# Journal: 2026-09-29-spec-fidelity-invention

<!-- fr:journal kind=discovery scope=plan id=p1-acceptance-via-set-status created=2026-09-29T07:59:22+00:00 phase=1 -->
### p1-acceptance-via-set-status · discovery · implement-phase's record cannot carry acceptance moves; rows moved with fr acceptance set-status (phase 1)

The shipped manifest's `implement-phase` emits `[journal:plan, plan:ticks]`, so its step
record has no `acceptance:` section (the pickup template omits it and `apply_record`
would refuse one). The three rows spec-fidelity-clause-partition,
spec-fidelity-design-inventory and spec-fidelity-remove-only were therefore moved to `ci`
with `fr acceptance set-status` (three `chore(fr): acceptance` commits on the branch,
reports regenerated, `fr acceptance check` green), which is the rule's sanctioned verb.

<!-- fr:journal kind=decision scope=plan id=p1-quote-boundary-is-a-clause-boundary created=2026-09-29T07:59:22+00:00 phase=1 -->
### p1-quote-boundary-is-a-clause-boundary · decision · A clause may not span two separate input quotes, as it may not span an elision (phase 1)

`check_fidelity` splits each `input` quote on the elision token and treats the end of
each quote as a fragment boundary too, so a clause never joins the tail of one source
quote to the head of the next. Spec §A names only the elision boundary; two separate
quotes are two separate pieces of the input, so the same reasoning (the text between
them is not part of the requirement's source) applies. Stricter, fail-closed.

<!-- fr:journal kind=decision scope=plan id=p1-fidelity-refuses-open-departures created=2026-09-29T07:59:22+00:00 phase=1 -->
### p1-fidelity-refuses-open-departures · decision · The fidelity witness holds every state but fixed/refuted, open included (phase 1)

Spec §D lists out-of-scope, deferred and unconfirmed. An `open` departure is also held
by `fidelity` (not only by `findings`), with the same `fr journal resolve ... --state
fixed` line, so the rule reads as one statement: a departure closes fixed or refuted.

<!-- fr:journal kind=decision scope=plan id=p1-none-behaviour-takes-none-backing created=2026-09-29T07:59:22+00:00 phase=1 -->
### p1-none-behaviour-takes-none-backing · decision · A `none` behaviour with a real backing is refused (phase 1)

Spec §B says a `none` backing is allowed only beside a `none` behaviour; the converse
(a `none` behaviour backed by `R1` or `invented s7`) is unspecified. `check_inventory`
refuses it, so an `invented` count can never exist without a behaviour.

<!-- fr:journal kind=discovery scope=plan id=p1-review-fixtures-carry-all-three-blocks created=2026-09-29T07:59:22+00:00 phase=1 -->
### p1-review-fixtures-carry-all-three-blocks · discovery · Test fixtures for the shipped spec-review now carry all three review blocks (phase 1)

`tests/unit/requirements_support.py` gained `DESIGN_SECTION`, `FIDELITY_BLOCK`,
`INVENTORY_BLOCK` and `REVIEW_BLOCKS`; `seed_requirements` inserts the Design section
BEFORE the Requirements table when a spec has neither (so tests that append requirement
rows still append to the table). `spec_review_support` and `test_record_apply` use
`REVIEW_BLOCKS`. Phase 2's `## Design inventory` PR-body tests can reuse them.

<!-- fr:journal kind=discovery scope=plan id=p1-reviewer-prose-still-says-unconfirmed created=2026-09-29T07:59:22+00:00 phase=1 -->
### p1-reviewer-prose-still-says-unconfirmed · discovery · fr-spec-reviewer prose and its test still name `unconfirmed` (phase 2, §G) (phase 1)

`tests/unit/test_spec_reviewer_agent.py::test_body_names_unconfirmed_as_the_resolution_for_invented_or_reinterpreted`
pins the reviewer agent's prose recommending `unconfirmed`, which phase 1 now refuses.
Left untouched here (the prose is §G, phase 2's scope); phase 2 must update both the
agent file and that test, plus the OpenCode/Hermes mirrors.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-29T07:59:22+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

The skeleton was written as the final module's shape (dataclasses, block locator, summary); T2 and T3 grew it in place, and T2.S3's refactor pass covered the shared helpers.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-29T07:59:22+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

check_inventory reuses fr.requirements' _parse_table and the module's own _one_block; the one new helper (_backing_problems) is already factored out, so nothing was duplicated to clean.

<!-- fr:journal kind=finding scope=plan id=p1-r1-duplicate-design-sections created=2026-09-29T08:15:05+00:00 phase=1 state=open review_scope=in -->
### p1-r1-duplicate-design-sections · finding [open] (reviewer: in scope) · Two same-named ### Design subsections always refused as out of order (phase 1)

fidelity.py parse_design_sections kept duplicates while check_inventory de-duplicated `seen`, so a spec with two `### Notes` got a false order refusal the reviewer could never satisfy, and InventoryCounts.sections double-counted. In scope: new code in this change.

<!-- fr:journal kind=finding scope=plan id=p1-r2-test-gaps created=2026-09-29T08:15:05+00:00 phase=1 state=open review_scope=in -->
### p1-r2-test-gaps · finding [open] (reviewer: in scope) · Missing tests: open/legacy-unconfirmed departures, quote-boundary clause, escaped quote, nested fence, duplicates; substring import guard (phase 1)

The behaviour was right but unpinned: a never-resolved departure and a legacy `unconfirmed` one at the witness, a clause spanning two separate quotes, a `\"` escape in a clause, a longer fence holding a shorter one, duplicate sections. The import-direction test was a bare substring check with an unclosed file. In scope: tests for this change.

<!-- fr:journal kind=finding scope=plan id=p1-r3-unconfirmed-refusal-shape created=2026-09-29T08:15:05+00:00 phase=1 state=open review_scope=in -->
### p1-r3-unconfirmed-refusal-shape · finding [open] (reviewer: in scope) · unconfirmed_refusal always refuses but kept a str | None type, unused params and a dead unconfirmed= write (phase 1)

After retirement the helper can only refuse; its Optional return, `del target, scope`, the callers' `is not None` checks and the `unconfirmed=res.state == "unconfirmed"` write were dead weight obscuring the retirement. In scope: code this change edited.

<!-- fr:journal kind=finding scope=plan id=p1-r4-backtick-info-string created=2026-09-29T08:15:05+00:00 phase=1 state=open review_scope=in -->
### p1-r4-backtick-info-string · finding [open] (reviewer: in scope) · A backtick run with a backtick in its info string opened a fence (phase 1)

_FENCE_RE treated "```inline``` text" at line start as a fence opener, swallowing the rest of the Design (CommonMark forbids a backtick in a backtick fence's info string). In scope: new parser in this change.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-09-29T08:15:05+00:00 phase=1 -->
### p1-review · review · phase 1 code review: 4 findings (r1-r4), all in scope, all fixed (phase 1)

Independent reviewer over d0d66c4a..9ba1748f against spec §A-§D, §H and Test Plan 1-4.
Findings: p1-r1-duplicate-design-sections, p1-r2-test-gaps, p1-r3-unconfirmed-refusal-shape,
p1-r4-backtick-info-string — each verified against the code and fixed in 8dd3156a with tests
(r1, r4 red first; r2's gap tests passed on first run, confirming the behaviour and pinning it).
Verified clean by the reviewer: clause-partition walk (whitespace, elision fragments, middle-column
pipe protection, escapes), CommonMark fence rules, the four run_cmd.py tables and both manifest
copies, predates handling, staged-resolve reading in the witness, unconfirmed still folding,
fr/requirements.py free of fr.fidelity. Out of scope, noted: fr/requirements.py `_locate_section`
remains fence-unaware (pre-existing; the spec limits the fence fix to the Design parser).

<!-- fr:journal kind=finding scope=plan id=p1-r1-duplicate-design-sections-resolved created=2026-09-29T08:15:05+00:00 phase=1 state=fixed resolves=p1-r1-duplicate-design-sections -->
### p1-r1-duplicate-design-sections-resolved · finding [fixed] · resolves p1-r1-duplicate-design-sections: Two same-named ### Design subsections always refused as out of order (phase 1)

parse_design_sections raises FidelityError naming duplicate section names (rename one); check_inventory reports it. Test: test_duplicate_design_section_names_are_refused_naming_them (8dd3156a).

<!-- fr:journal kind=finding scope=plan id=p1-r2-test-gaps-resolved created=2026-09-29T08:15:05+00:00 phase=1 state=fixed resolves=p1-r2-test-gaps -->
### p1-r2-test-gaps-resolved · finding [fixed] · resolves p1-r2-test-gaps: Missing tests: open/legacy-unconfirmed departures, quote-boundary clause, escaped quote, nested fence, duplicates; substring import guard (phase 1)

Added test_a_departure_left_open_or_legacy_unconfirmed_is_refused (4 cases), clause-spans-two-quotes param, test_a_clause_holding_an_escaped_quote_parses, test_a_longer_fence_is_not_closed_by_a_shorter_one, the duplicate-section test, and an AST-based import-direction check (8dd3156a).

<!-- fr:journal kind=finding scope=plan id=p1-r3-unconfirmed-refusal-shape-resolved created=2026-09-29T08:15:05+00:00 phase=1 state=fixed resolves=p1-r3-unconfirmed-refusal-shape -->
### p1-r3-unconfirmed-refusal-shape-resolved · finding [fixed] · resolves p1-r3-unconfirmed-refusal-shape: unconfirmed_refusal always refuses but kept a str | None type, unused params and a dead unconfirmed= write (phase 1)

unconfirmed_refusal(finding_id) -> str; _refuse_unconfirmed raises directly; callers drop the None check; the unreachable unconfirmed= write removed (the fold still reads existing records) (8dd3156a).

<!-- fr:journal kind=finding scope=plan id=p1-r4-backtick-info-string-resolved created=2026-09-29T08:15:05+00:00 phase=1 state=fixed resolves=p1-r4-backtick-info-string -->
### p1-r4-backtick-info-string-resolved · finding [fixed] · resolves p1-r4-backtick-info-string: A backtick run with a backtick in its info string opened a fence (phase 1)

A backtick run whose info string holds a backtick no longer opens a fence. Test: test_a_backtick_run_with_a_backtick_in_its_info_string_is_not_a_fence (8dd3156a).
