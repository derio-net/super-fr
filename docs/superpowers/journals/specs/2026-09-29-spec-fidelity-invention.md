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
