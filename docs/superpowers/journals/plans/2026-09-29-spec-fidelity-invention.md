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

<!-- fr:journal kind=discovery scope=plan id=p2-acceptance-via-set-status created=2026-09-29T08:29:58+00:00 phase=2 -->
### p2-acceptance-via-set-status · discovery · Acceptance rows moved with `fr acceptance set-status` (phase 2) (phase 2)

An implement-phase record cannot carry `acceptance:`, so
spec-fidelity-delegated-decisions and spec-fidelity-pr-design-inventory were moved to `ci`
with `fr acceptance set-status ... --level unit=...` (commits 10dce7cc, b10a29c8);
`fr acceptance check` is green.

<!-- fr:journal kind=discovery scope=plan id=p2-traced-fixture-cannot-carry-fidelity created=2026-09-29T08:29:58+00:00 phase=2 -->
### p2-traced-fixture-cannot-carry-fidelity · discovery · The legacy-unconfirmed PR-body fixture cannot coexist with live fidelity evidence (phase 2) (phase 2)

test_deliver_pr_body's `_traced_run_at_deliver` holds an `unconfirmed` spec finding,
which the `fidelity` witness always refuses. The Design-inventory tests therefore patch
the loaded state with `fidelity` evidence naming a second review entry (`_with_fidelity`)
rather than deriving it live. The delegated listing precedes any legacy unconfirmed line.

<!-- fr:journal kind=discovery scope=plan id=p2-inventory-block-extractor created=2026-09-29T08:29:58+00:00 phase=2 -->
### p2-inventory-block-extractor · discovery · fr.fidelity gained a public inventory_block extractor (phase 2) (phase 2)

Phase 1's module only had the private `_one_block`; the PR body needs the fenced block
itself (fences included, like `coverage_block`), so `inventory_block(review_body)` was added
beside it and returns None unless there is exactly one block.

<!-- fr:journal kind=discovery scope=plan id=p2-brainstorming-skill-line-cap created=2026-09-29T08:29:58+00:00 phase=2 -->
### p2-brainstorming-skill-line-cap · discovery · fr-brainstorming SKILL.md sits at the 120-line cap (phase 2) (phase 2)

test_under_120_lines forced the delegated-answer sentence onto one long line instead of
five wrapped ones. Further additions there need trimming elsewhere.

<!-- fr:journal kind=discovery scope=plan id=p2-explainer-regenerated created=2026-09-29T08:29:58+00:00 phase=2 -->
### p2-explainer-regenerated · discovery · 01-fr-goal.html regenerated; renderer verified byte-identical first (phase 2) (phase 2)

The blog-craft renderer resolved at the marketplace path. Run from `/` with
`uv run --isolated --no-project --with markdown --with pyyaml`, the unmodified .md
re-rendered byte-identical to the committed .html; after the prose edit only the edited
paragraphs changed. test_tripwire_explainers_fresh is green. Nothing owed.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-09-29T08:29:58+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

one new field threaded through existing seams (model, parse, CLI, record item); the migration module is a copy of record_visual by design, nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-09-29T08:29:58+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

the new _design_inventory deliberately mirrors _input_coverage; extracting a shared helper would couple two sections whose miss-messages differ
