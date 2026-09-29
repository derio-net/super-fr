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
