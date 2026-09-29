# Journal: 2026-09-29-spec-fidelity-invention

<!-- fr:journal kind=discovery scope=spec id=input-batch-brief created=2026-09-29T07:18:34+00:00 input=true -->
### input-batch-brief · discovery · Raw input: batch spec-fidelity dispatch brief (verbatim)

/fr-goal Spec review checks fidelity and invention, not coverage alone

Batch `spec-fidelity` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#773: Spec review checks coverage, not clause fidelity or invention: dropped clauses and invented UI behaviour pass (#759 follow-up)
Operator-prioritised. spec-review checks coverage (every input span maps to a requirement), not fidelity (the requirement keeps the span's meaning) or invention (Design adds user-visible behaviour no requirement backs). Take 9 (fr 4.29.2): an invented card-click toggle shipped again with 0 invented/reinterpreted findings; clauses ("same style", "same layout", the range label) dropped from requirement text.
Note: Main #759 follow-up. Batch `spec-fidelity` (wave 7), after `requirements-gate`. Talk cut line: if not merged by Wednesday evening, take 10's fr arm records without it.

## Why these belong together
Wave 7, after requirements-gate (shared spec-review record shape, fr/requirements.py); the fix for take 9's card-click invention. The spec reviewer also checks that each requirement keeps its span's meaning and that Design adds no user-visible behaviour a requirement does not back; invented/reinterpreted findings block. Cut line from the talk plan: if it is not merged by Wednesday evening, take 10's fr arm is recorded without it and the scorecard says so.

## Delivery rules
- Work on branch `feat/batch-spec-fidelity`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#773
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=discovery scope=spec id=input-issue-773 created=2026-09-29T07:18:34+00:00 input=true -->
### input-issue-773 · discovery · Raw input: issue #773 title and body (verbatim; one repo name redacted to example-user/example-playground)

Spec review checks coverage, not clause fidelity or invention: dropped clauses and invented UI behaviour pass (#759 follow-up)

## What happened

Follow-up to #759. Take 9 of the super-fr-3 feature-C recording (fr 4.29.2, same brief as take 8) shows the new structure working: a `## Requirements` section R1–R11 quoting the brief, the raw brief in the spec journal, and the spec reviewer returning a 45-span coverage table. But the review checks *coverage* (every input span maps to a requirement id), not *fidelity* (the requirement keeps the span's meaning) or *invention* (Design adds user-visible behaviour no requirement backs). Everything below passed with 0 `invented` / `reinterpreted` findings, and the MR said "Built without operator confirmation: None":

- **Invented:** "selectable article cards": a card click adds or removes the article. The brief says "− / + on each article card (1–20)" and nothing about card clicks. The same invention as take 8 (the reason #759 was filed); it shipped again as a defect (card click turns beer 3 → 0).
- **Invented:** a new always-accepted demo article ("Fresh Produce"); a configurable server port.
- **Clauses dropped from the requirement text:** "a number field *in the same style*", "*the same layout*", the "✓ 680–720 g" range label, "checked … *against the single-article view*", the legend saying "basket". Some survive only inside the Source quote; the downstream agents implement the requirement text. The shipped chart kept the single-article legend ("GMM total / Component(s)").

Evidence: take 9 spec `docs/superpowers/specs/2026-09-28-basket-weight-check-design.md` at `2edcb24` (example-user/example-playground), reviewer session `ses_f176d6a6…`; scorecard `score/scorecard-9.md` in super-fr-3.

## Expected

The spec reviewer (and fr's check of its output) also returns, per requirement and per Design section:

1. **Clause fidelity:** for each requirement, the clauses of its source quote that the requirement text drops or weakens (`reinterpreted`, in scope).
2. **Invention:** every user-visible behaviour in Design (interactions, new demo data, new config) that no requirement or recorded decision backs (`invented`, in scope). An invented behaviour is either removed or raised as an operator question, as #759 intended; "Your call." answers are recorded as delegated decisions.

The MR's "Built without operator confirmation" section lists whatever survives.

<!-- fr:journal kind=decision scope=spec id=d1-remove-only created=2026-09-29T07:18:34+00:00 -->
### d1-remove-only · decision · Invented/reinterpreted spec-review findings are removed, never asked, never unconfirmed

Operator (round 1 q1): 'Remove only, never ask'. An invented or reinterpreted finding raised at spec-review is fixed by removing the departure (invented behaviour deleted; reinterpreted requirement restored to its quote's literal reading). The operator is not asked at spec-review; `unconfirmed` is retired for new writes. Supersedes d3-late-unconfirmed of the 2026-09-28 requirements-traceability spec.

<!-- fr:journal kind=decision scope=spec id=d2-clause-drop-reinterpreted created=2026-09-29T07:18:34+00:00 -->
### d2-clause-drop-reinterpreted · decision · A dropped or weakened clause of a requirement's own quote is a reinterpreted finding

Operator (round 1 q2): 'Treat as reinterpreted'. Handled by d1-remove-only: the clause is restored.

<!-- fr:journal kind=decision scope=spec id=d3-clause-partition created=2026-09-29T07:18:34+00:00 -->
### d3-clause-partition · decision · Per-requirement fidelity output is a clause partition fr verifies

Operator (round 1 q3): 'Clause partition'. For each requirement with an input source, the reviewer cuts its quotes into clauses labelled `kept` or a finding id; fr verifies the clauses partition the quotes, like input-coverage.

<!-- fr:journal kind=decision scope=spec id=d4-design-inventory created=2026-09-29T07:18:34+00:00 -->
### d4-design-inventory · decision · The reviewer inventories every Design subsection; fr verifies it

Operator (round 1 q4): 'Inventory every section'. Every `###` subsection of `## Design`, in order, with each user-visible behaviour backed by `R<n>`, `decision <id>` or `invented <finding-id>`, or `none`. fr refuses a missing or reordered section, an unknown id, or a finding not in the spec journal.

<!-- fr:journal kind=decision scope=spec id=d5-delegated-flag created=2026-09-29T07:18:34+00:00 -->
### d5-delegated-flag · decision · "Your call." answers carry a `delegated` flag on the decision entry

Operator (round 1 q5): 'A `delegated` flag'. Journal header token `delegated=true` plus a record stamp bump and migration. Still a valid requirement source. The PR's 'Built without operator confirmation' section lists every delegated decision and the requirements citing it. Applies to every question round.

<!-- fr:journal kind=decision scope=spec id=d6-pr-design-inventory created=2026-09-29T07:18:34+00:00 -->
### d6-pr-design-inventory · decision · The PR body renders the design inventory, not the fidelity block

Operator (round 1 q6): 'Design inventory only'. A required `## Design inventory` section inside <details>; fidelity problems already appear as findings.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-29T07:25:26+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · §C wiring of `fidelity` names two of the five places `coverage` is wired

check: codebase
evidence: spec §C, §F, §H; packages/fr/src/fr/commands/run_cmd.py:1389-1399, 1402-1407, 1416-1431, 1862; packages/fr/src/fr/workflows/fr-goal.yaml:102; packages/fr/src/fr/record/pr_body.py:124-141
scope: the new evidence name is this change's, and a partial wiring either refuses spec-review as unverifiable or leaves the wheel manifest and the PR body's predates handling behind
§C says `fidelity` "joins `_REQUIREMENTS_EVIDENCE` and the derived-name set". run_cmd.py wires a derived requirements witness in THREE tables: `_VERIFIABLE_EVIDENCE` (:1389), `_DERIVED_EVIDENCE` (:1405) and `_DERIVED_FROM` (:1416). The comment at :1402-1404 says "all three in all three tables, or resolve refuses the step as unverifiable". The manifest also has a wheel copy, packages/fr/src/fr/workflows/fr-goal.yaml:102, which the README says is regenerated with `cp` and which test_tripwire_shipped_workflows.py guards. §C names only plugins/super-fr/workflows/fr-goal.yaml. Last, §H has a pre-gate run record `fidelity = REQUIREMENTS_PREDATES` through `_requirements_witnesses` (:1956-1957). §F's Design-inventory predates test only checks whether any `fidelity` evidence exists, so the predates string would count as evidence. That differs from `pr_body._predates_gate` (:137-141), which checks for the predates string by name. To fix, name all three tables, the wheel copy and the `_predates_gate` extension (or define §F's predates test the same way `_predates_gate` does).

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-29T07:25:26+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · `_protect_span_pipes` cannot protect a clause in the middle column of the requirement-fidelity row

check: codebase
evidence: spec §A ("follows the input-coverage span grammar in `fr.requirements` (`_protect_span_pipes`, the `\|`/`\"` escapes)"); packages/fr/src/fr/requirements.py:485, 493-500
scope: the block grammar is new in this change, and as specified it breaks on the #777 input shape (an input that quotes a Markdown table)
`_QUOTED_SPAN_ROW_RE` (`^(\s*\|\s*")(.*)("\s*\|[^|"]*\|\s*)$`) only matches a row whose FIRST cell is the quoted span, followed by one label cell. A `requirement-fidelity` row is `| R1 | "clause" | kept |`, so the quote sits in the middle column and the regex never matches. A raw `|` inside a clause then splits the row, which is exactly the #777 failure that coverage was fixed for. §A should specify a three-column variant of the protection (quoted middle cell) and a Test Plan case for a clause containing `|`. The same applies to the design-inventory `behaviour` cell, which is unquoted, so either state that a `|` there must be escaped or quote the cell.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-29T07:25:26+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · Test Plan refuses a clause crossing an elision, but §A's comparison removes the elision and cannot detect one

check: consistency
evidence: spec §A ("with the quote's elision token (` … `) removed as well, because an elision joins two quoted fragments and no clause can contain it") vs Test Plan 1 ("a clause crossing an elision ... refused"); packages/fr/src/fr/requirements.py:318
scope: an internal contradiction between this spec's design and its own Test Plan
Take a quote `A … B`. With the ellipsis removed before comparison, both sides normalise to `AB`, so a single clause `"A B"` (or `"AB"`) passes the equality check just as `"A"` + `"B"` does. The design therefore accepts the very case Test Plan 1 says is refused. The only case it rejects is a clause that literally contains ` … `. To match the Test Plan, §A should also require every fragment boundary (a split on `ELLIPSIS`) to coincide with a clause boundary. Otherwise drop that case from the Test Plan.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-29T07:25:26+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · §A exempts requirements added after the review from the clause partition d3 demands for every input-sourced requirement

check: decisions
evidence: decision d3-clause-partition ("For each requirement with an input source, the reviewer cuts its quotes into clauses"); spec §A paragraph "Completeness is taken over the requirements the reviewer saw ... is exempt"
scope: narrowing an operator decision is this spec's own departure; unsure whether the operator would accept it, so tagged in scope
d3 applies to every requirement with an input source. §A exempts a requirement added after the review to fix a `dropped` finding, and that is the requirement no reviewer has read. Its text is never fidelity-checked, so the clause-dropping this change targets (take 9's "same style" / "same layout") can come back through the dropped-finding fix path. To honour d3, demand rows for every input-sourced requirement at resolve, so that adding one forces a reviewer re-dispatch (§C already accepts that cost for renamed sections). Alternatively, raise the exemption with the operator rather than deciding it in the spec.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-09-29T07:25:26+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · §G leaves fr-goal SKILL.md §8 (PR-body sections) and §1 (question answers) describing the old behaviour

check: consistency
evidence: spec §G (names only fr-goal §2 and fr-brainstorming §1); plugins/super-fr/skills/fr-goal/SKILL.md:108 ("the spec findings resolved `unconfirmed` (`## Built without operator confirmation`, or "None.")", with no `## Design inventory`); plugins/super-fr/skills/fr-goal/SKILL.md:53 ("Each answer is a `decision` in the brainstorm record"); decision d5-delegated-flag ("Applies to every question round")
scope: stale prose about surfaces this change modifies; it is not pre-existing
§F changes what `## Built without operator confirmation` holds (delegated decisions) and adds a required `## Design inventory`. fr-goal §8 lists the PR body's sections and still describes the section as unconfirmed findings, and it omits the new one. The questions fr-goal asks are recorded by fr-goal §1, which gives no way to mark a "Your call." answer `delegated: true`, while d5 says the flag applies to every question round. §G should add fr-goal §1 and §8, with mirrors regenerated as it already states.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-09-29T07:25:26+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · §E's record 4→5 bump names the migration module but not its import or the second version constant

check: codebase
evidence: spec §E ("the stamp moves 4 → 5 with a stamp-only migration, `fr.artifacts.record_delegated`, following `record_input_unconfirmed`"); packages/fr/src/fr/artifacts/registry.py:441; packages/fr/src/fr/record/model.py:54; packages/fr/src/fr/artifacts/__init__.py:51-53; .claude/rules/artifact-versioning.md (items 1-3, "A migration nobody imports never runs")
scope: the shape change is this spec's, and the rule's obligations are part of its shipped scope
The bump is correct and stamp-only is enough, because `delegated` is additive and nothing moves, so no frozen legacy model is owed. It is under-specified against the rule, though. The stamp lives in two constants (`registry.py:441` `current_version=4` and `record/model.py:54` `RECORD_SCHEMA_VERSION = 4`), and the migration only runs if `fr/artifacts/__init__.py` imports it (the precedent is :53, `record_visual`, the 3→4 hop, which is the closer template than `record_input_unconfirmed`). Name both constants, the import, and a Test Plan assertion that the record chain reaches 5 hop by hop.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-29T07:25:26+00:00 -->
### spec-review · review · independent spec review: 6 findings

input-coverage:
```input-coverage
| span | coverage |
|---|---|
| "/fr-goal Spec review checks fidelity and invention, not coverage alone" | context |
| "Batch `spec-fidelity` of derio-net/super-fr: 1 issues, delivered as ONE pull request." | context |
| "## super-fr#773: Spec review checks coverage, not clause fidelity or invention: dropped clauses and invented UI behaviour pass (#759 follow-up)" | context |
| "Operator-prioritised. spec-review checks coverage (every input span maps to a requirement), not fidelity (the requirement keeps the span's meaning) or invention (Design adds user-visible behaviour no requirement backs)." | R1, R2 |
| "Take 9 (fr 4.29.2): an invented card-click toggle shipped again with 0 invented/reinterpreted findings; clauses ("same style", "same layout", the range label) dropped from requirement text." | context |
| "Note: Main #759 follow-up. Batch `spec-fidelity` (wave 7), after `requirements-gate`. Talk cut line: if not merged by Wednesday evening, take 10's fr arm records without it." | context |
| "## Why these belong together" | context |
| "Wave 7, after requirements-gate (shared spec-review record shape, fr/requirements.py); the fix for take 9's card-click invention." | context |
| "The spec reviewer also checks that each requirement keeps its span's meaning" | R1 |
| "and that Design adds no user-visible behaviour a requirement does not back;" | R2 |
| "invented/reinterpreted findings block." | R4 |
| "Cut line from the talk plan: if it is not merged by Wednesday evening, take 10's fr arm is recorded without it and the scorecard says so." | context |
| "## Delivery rules" | context |
| "- Work on branch `feat/batch-spec-fidelity`." | deferred |
| "- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:" | deferred |
| "Closes derio-net/super-fr#773" | context |
| "- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels." | deferred |
| "Spec review checks coverage, not clause fidelity or invention: dropped clauses and invented UI behaviour pass (#759 follow-up)" | context |
| "## What happened" | context |
| "Follow-up to #759. Take 9 of the super-fr-3 feature-C recording (fr 4.29.2, same brief as take 8) shows the new structure working: a `## Requirements` section R1–R11 quoting the brief, the raw brief in the spec journal, and the spec reviewer returning a 45-span coverage table. But the review checks *coverage* (every input span maps to a requirement id), not *fidelity* (the requirement keeps the span's meaning) or *invention* (Design adds user-visible behaviour no requirement backs). Everything below passed with 0 `invented` / `reinterpreted` findings, and the MR said "Built without operator confirmation: None":" | context |
| "- **Invented:** "selectable article cards": a card click adds or removes the article. The brief says "− / + on each article card (1–20)" and nothing about card clicks. The same invention as take 8 (the reason #759 was filed); it shipped again as a defect (card click turns beer 3 → 0)." | context |
| "- **Invented:** a new always-accepted demo article ("Fresh Produce"); a configurable server port." | context |
| "- **Clauses dropped from the requirement text:** "a number field *in the same style*", "*the same layout*", the "✓ 680–720 g" range label, "checked … *against the single-article view*", the legend saying "basket". Some survive only inside the Source quote; the downstream agents implement the requirement text. The shipped chart kept the single-article legend ("GMM total / Component(s)")." | context |
| "Evidence: take 9 spec `docs/superpowers/specs/2026-09-28-basket-weight-check-design.md` at `2edcb24` (example-user/example-playground), reviewer session `ses_f176d6a6…`; scorecard `score/scorecard-9.md` in super-fr-3." | context |
| "## Expected" | context |
| "The spec reviewer (and fr's check of its output) also returns, per requirement and per Design section:" | R3 |
| "1. **Clause fidelity:** for each requirement, the clauses of its source quote that the requirement text drops or weakens (`reinterpreted`, in scope)." | R1, R3 |
| "2. **Invention:** every user-visible behaviour in Design (interactions, new demo data, new config) that no requirement or recorded decision backs (`invented`, in scope)." | R2, R3 |
| "An invented behaviour is either removed" | R4 |
| "or raised as an operator question, as #759 intended;" | deferred |
| ""Your call." answers are recorded as delegated decisions." | R5 |
| "The MR's "Built without operator confirmation" section lists whatever survives." | R6 |
```
verified:
- packages/fr/src/fr/commands/run_cmd.py:1862 — `_REQUIREMENTS_EVIDENCE = ("requirements", "coverage", "requirement-rows")`
- packages/fr/src/fr/commands/run_cmd.py:1405 — `_DERIVED_EVIDENCE` derived-name set (see s1 for `_VERIFIABLE_EVIDENCE` :1389 and `_DERIVED_FROM` :1416)
- packages/fr/src/fr/commands/run_cmd.py:1881-1896 — `_predates_requirements`; :1956-1957 records REQUIREMENTS_PREDATES for every wanted name, so §H's "existing predates line for `fidelity`" holds once `fidelity` joins the tuple
- packages/fr/src/fr/commands/run_cmd.py:1989-2027 — `_coverage_witness` reads the `kind=review` entry named by `review` from the capture's spec-journal entries; a sibling witness can read the same entry
- packages/fr/src/fr/commands/run_cmd.py:1716-1724 — the `review` gate runs before the derived witnesses
- packages/fr/src/fr/requirements.py:148 — `_locate_section` ends a section at the first `## ` line and is not fence-aware (the §B claim is correct)
- docs/superpowers/implemented/specs/2026-09-28-requirements-traceability-design.md:130-131 — a fenced `## Requirements` at line 131, as §B says
- packages/fr/src/fr/requirements.py — 629 lines, as §C says
- packages/fr/src/fr/requirements.py:270 — `parse_requirements`
- packages/fr/src/fr/requirements.py:512 — `coverage_block`
- packages/fr/src/fr/requirements.py:519 — `check_coverage` (whitespace-stripped `_coverage_form` comparison, :503-509)
- packages/fr/src/fr/requirements.py:487 — `_REDISPATCH`
- packages/fr/src/fr/requirements.py:493 — `_protect_span_pipes` (exists; see s2 for its row shape)
- packages/fr/src/fr/requirements.py:318 — `ELLIPSIS = " … "`
- packages/fr/src/fr/requirements.py:73 — `REQUIREMENTS_PREDATES`
- packages/fr/src/fr/commands/journal_cmd.py:420 — `if state == "unconfirmed":` refusal point, as cited
- packages/fr/src/fr/commands/journal_cmd.py:306 — `RESOLUTION_STATES` includes `unconfirmed`
- packages/fr/src/fr/record/apply.py:251 — `unconfirmed_refusal`, shared by `fr journal resolve` and record apply (:387-388), so refusing there covers both writers; no other writer of `unconfirmed` found in packages/fr/src
- packages/fr/src/fr/record/model.py:69 — `ResolutionState` includes `unconfirmed`
- packages/fr/src/fr/record/model.py:107-126 — `JournalItem` is `_Strict` (`extra="forbid"`, :79-80), so `delegated` is a record shape change
- packages/fr/src/fr/journal/model.py:123, 259-273, 360-376 — `input=true` token carried via `_HEADER_FIELDS` and named-key parse; unknown tokens ignored, so `delegated=true` needs no journal bump (§E claim holds)
- packages/fr/src/fr/artifacts/registry.py:441 — record `current_version=4`
- packages/fr/src/fr/artifacts/record_input_unconfirmed.py:23-34 — stamp-only `SchemaMigration` with `guard_record`, the pattern §E follows
- packages/fr/src/fr/artifacts/__init__.py:51-53 — record migration imports (questions, input_unconfirmed, visual)
- packages/fr/src/fr/record/pr_body.py:42-50 — `REQUIRED_SECTIONS`, with `## Input coverage` before `## Post-merge verification owed`
- packages/fr/src/fr/record/pr_body.py:61 — `missing_sections`
- packages/fr/src/fr/record/pr_body.py:94-117 — legacy `unconfirmed` bucket rendered under `## Built without operator confirmation`
- packages/fr/src/fr/record/template.py:94 — the `unconfirmed` comment line §G replaces
- plugins/super-fr/workflows/fr-goal.yaml:74, 102 — `spec-review` step, `evidence: [review, reviewer, findings, requirements, coverage]`
- plugins/super-fr/agents/fr-spec-reviewer.md:62, 92 — "Faithful"/"Nothing invented" checks and the `unconfirmed` resolution guidance §G rewrites
- plugins/super-fr/skills/fr-goal/SKILL.md:58 — §2 resolves invented/reinterpreted as `--state unconfirmed`
- plugins/super-fr/skills/fr-brainstorming/SKILL.md:55 — §1 "Record the input, then brainstorm" exists
- docs/explainers/01-fr-goal.md:221, 619 — names coverage and `unconfirmed`, as §I says

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-29T07:25:26+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: §C wiring of `fidelity` names two of the five places `coverage` is wired

§C now names all four run_cmd.py tables (_VERIFIABLE_EVIDENCE, _DERIVED_EVIDENCE, _DERIVED_FROM, _REQUIREMENTS_EVIDENCE) and both manifest copies; §F's predates test extends pr_body._predates_gate by name (absent OR REQUIREMENTS_PREDATES). Test Plan 6 and 7 cover it.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-29T07:25:26+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: `_protect_span_pipes` cannot protect a clause in the middle column of the requirement-fidelity row

§A specifies a three-column pipe-protection variant (quoted middle cell); §B requires `\|` in the unquoted behaviour cell. Test Plan 1 and 2 add the `|` cases.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-29T07:25:26+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: Test Plan refuses a clause crossing an elision, but §A's comparison removes the elision and cannot detect one

§A now splits each quote on ELLIPSIS into fragments and requires every fragment boundary to be a clause boundary; Test Plan 1 refuses a clause spanning an elision boundary.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-29T07:25:26+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: §A exempts requirements added after the review from the clause partition d3 demands for every input-sourced requirement

§A honours d3 as written: every input-sourced requirement at resolve needs rows, so a requirement added after the review forces a reviewer re-dispatch. Test Plan 1 refuses one added after the review.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-09-29T07:25:26+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: §G leaves fr-goal SKILL.md §8 (PR-body sections) and §1 (question answers) describing the old behaviour

§G adds fr-goal SKILL.md §1 (a 'Your call.' answer recorded delegated: true) and §8 (the section list: delegated decisions, `## Design inventory`).

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-09-29T07:25:26+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: §E's record 4→5 bump names the migration module but not its import or the second version constant

§E names both constants (registry.py:441, record/model.py:54), the record_visual template, the __init__.py import, and states no frozen legacy model is owed; Test Plan 5 asserts the chain [2, 3, 4, 5].

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-09-29-spec-fidelity-invention-p2 created=2026-09-29T07:27:07+00:00 -->
### phase-split-2026-09-29-spec-fidelity-invention-p2 · decision · ask: R5–R7 (delegated decisions, PR body, prose) are independently reviewable from the R1–R4 check
