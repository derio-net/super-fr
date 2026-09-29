# Spec review checks fidelity and invention, not coverage alone

**Status:** design · **Date:** 2026-09-29 · **Closes:** super-fr#773
**Builds on:** `docs/superpowers/implemented/specs/2026-09-28-requirements-traceability-design.md`
(super-fr#759: the `## Requirements` grammar, the `input-coverage` partition,
the `unconfirmed` resolution)

## Background

The requirements-traceability change (#759) gave spec review a structural
check for **coverage**: the reviewer partitions the whole input into spans,
each labelled with the requirement ids that cover it, and fr refuses a
partition with a gap. It left two other questions to the reviewer's
judgement:

- **fidelity:** does a requirement keep the meaning of the span it quotes?
- **invention:** does `## Design` add user-visible behaviour that no
  requirement backs?

Take 9 of the talk's feature-C recording (fr 4.29.2) shows the result.
Coverage was complete: 45 spans, every one labelled. The review raised no
`invented` or `reinterpreted` finding, yet the spec had invented a card-click
toggle (the same invention #759 was filed for) and its requirement text had
dropped clauses the quotes still carried ("in the same style", "the same
layout", the range label). Downstream agents implement the requirement text,
not the quote beside it, so the dropped clauses were never built.

The reviewer prose already asks for both checks
(`plugins/super-fr/agents/fr-spec-reviewer.md`, "Faithful" and "Nothing
invented"). Asking was not enough. This change applies #759's remedy for
coverage to fidelity and invention: the reviewer returns a complete,
checkable account, and fr refuses an incomplete one. A skimmed requirement or
an unread Design section then produces a refusal instead of a clean review.

It also retires #759's d3-late-unconfirmed. An invented or reinterpreted
finding is no longer kept and listed for a veto at merge. It is removed.

## Decisions (operator, 2026-09-29)

| id | decision |
|---|---|
| d1-remove-only | An invented or reinterpreted finding raised at spec-review is fixed by removing the departure: the invented behaviour is deleted, and a reinterpreted requirement is restored to the literal reading of its quote. The operator is never asked at spec-review, and such a finding is no longer closed as `unconfirmed`. This supersedes d3-late-unconfirmed of the 2026-09-28 spec. |
| d2-clause-drop-reinterpreted | A requirement whose text drops or weakens a clause of its own source quote is a `reinterpreted` finding, handled by d1 (restore the clause). |
| d3-clause-partition | The reviewer's per-requirement fidelity output partitions each requirement's quotes into clauses, each labelled `kept` or with a finding id, and fr verifies the partition, as it does for input-coverage. |
| d4-design-inventory | The reviewer returns an inventory of every `###` subsection of `## Design`, in order, listing each user-visible behaviour with its backing (`R<n>`, `decision <id>`, or `invented <finding-id>`), or `none`. fr refuses a missing or reordered section, an unknown id, or a finding that is not in the spec journal. |
| d5-delegated-flag | A "Your call." answer is recorded as a decision journal entry carrying `delegated=true`: a journal header token, plus a record-kind stamp bump and migration. It remains a valid requirement source. The PR's "Built without operator confirmation" section lists every delegated decision and the requirements that cite it. This applies to every question round. |
| d6-pr-design-inventory | The PR body gains a required `## Design inventory` section rendering the inventory inside `<details>`. The fidelity block is not rendered, because its problems already appear as findings. |

## Requirements

| id | requirement | source |
|---|---|---|
| R1 | Spec review checks, for every requirement, that the requirement text keeps every clause of its source quote. A clause the text drops or weakens is a `reinterpreted` finding, in scope. | input "The spec reviewer also checks that each requirement keeps its span's meaning"<br>input "for each requirement, the clauses of its source quote that the requirement text drops or weakens (`reinterpreted`, in scope)."<br>decision d2-clause-drop-reinterpreted |
| R2 | Spec review checks, for every Design section, that each user-visible behaviour it adds (interactions, demo data, configuration) is backed by a requirement or a recorded decision. An unbacked behaviour is an `invented` finding, in scope. | input "and that Design adds no user-visible behaviour a requirement does not back"<br>input "every user-visible behaviour in Design (interactions, new demo data, new config) that no requirement or recorded decision backs (`invented`, in scope)." |
| R3 | fr checks the reviewer's output: a per-requirement clause account that covers every quoted clause, and a per-Design-section inventory that covers every section. It refuses a review that leaves any of either unaccounted for. | input "The spec reviewer (and fr's check of its output) also returns, per requirement and per Design section:"<br>decision d3-clause-partition<br>decision d4-design-inventory |
| R4 | Invented and reinterpreted findings block spec-review until the departure is removed (or the finding refuted). They can no longer be closed as built without operator confirmation. | input "invented/reinterpreted findings block."<br>input "An invented behaviour is either removed"<br>decision d1-remove-only |
| R5 | A "Your call." answer to a question is recorded as a delegated decision, distinguishable by fr from a decision the operator made. | input ""Your call." answers are recorded as delegated decisions."<br>decision d5-delegated-flag |
| R6 | The PR's "Built without operator confirmation" section lists what survives without the operator's own decision: every delegated decision and the requirements citing it. | input "The MR's "Built without operator confirmation" section lists whatever survives."<br>decision d5-delegated-flag |
| R7 | The PR body shows the design inventory, so the operator can see every user-visible behaviour and its backing at merge. | decision d6-pr-design-inventory |

## Deferred from input

| input | reason |
|---|---|
| "or raised as an operator question, as #759 intended;" | Rejected by d1-remove-only: spec-review never reopens the operator gate; the departure is removed. |
| "Work on branch `feat/batch-spec-fidelity`." | A delivery instruction for this run, not product behaviour; the run follows it. |
| "Open a draft PR as soon as the spec is committed." | A delivery instruction for this run, not product behaviour; the run follows it. |
| "Do not name any member issue as a phase `tracking_issue` in the plan" | A delivery instruction for this run's plan, not product behaviour; the plan follows it. |

## Design

### A. The `requirement-fidelity` block (R1, R3)

Inside the body of its `kind: review` spec-journal entry (the entry
`evidence.review` names, the one that already carries `input-coverage`), the
reviewer returns a second fenced block:

````markdown
```requirement-fidelity
| requirement | clause | fidelity |
|---|---|---|
| R1 | "a number field in the same style" | s4 |
| R1 | "as the article view" | kept |
| R2 | "− / + on each article card" | kept |
| R2 | "(1–20)" | kept |
```
````

- **requirement:** a requirement id.
- **clause:** a verbatim piece of that requirement's `input` quotes. The cell
  follows the input-coverage span grammar in
  `fr.requirements` (`_protect_span_pipes`, the `\|`/`\"` escapes).
- **fidelity:** `kept` (the requirement text carries the clause's meaning) or
  a finding id (a `kind=finding` spec-journal entry, the `reinterpreted`
  finding raised for the clause).

The rows of one requirement are contiguous, and requirements appear in
`## Requirements` table order. A requirement's clauses, concatenated in table
order, EQUAL its `input` quotes concatenated in source order. The comparison
is the same whitespace-insensitive one `check_coverage` uses, with the
quote's elision token (` … `) removed as well, because an elision joins two
quoted fragments and no clause can contain it. A decision-only requirement
has no rows, since it has no quote to be faithful to.

Completeness is taken over the requirements the reviewer saw. Every
requirement with an `input` source that the review's own `input-coverage`
block cites must have rows. A requirement added after the review, to fix a
`dropped` finding, is exempt; its span was labelled `missing <id>`, so the
review never saw it.

### B. The `design-inventory` block (R2, R3)

In the same review entry the reviewer returns a third block:

````markdown
```design-inventory
| section | behaviour | backing |
|---|---|---|
| A. Quantities | − / + on each card, 1–20 | R2 |
| A. Quantities | clicking a card adds or removes the article | invented s7 |
| B. Storage | none | none |
```
````

- **section:** the text of a `###` heading inside `## Design`, without the
  `### ` marker. A `## Design` with no `###` subsection is one section named
  `Design`.
- **behaviour:** one user-visible behaviour the section adds (an interaction,
  output, demo data, a configuration key, a default) in the reviewer's words,
  or `none` when the section adds none.
- **backing:** one or more of `R<n>` and `decision <id>`, comma-separated;
  `invented <finding-id>`; or `none`, which is allowed only beside a `none`
  behaviour.

fr checks that:

1. every `###` subsection of `## Design` appears, in document order, with at
   least one row, and its rows are contiguous; no section name is unknown;
2. every `R<n>` is in the Requirements table and every `decision <id>` names a
   `kind=decision` spec-journal entry;
3. every `invented <id>` names a `kind=finding` spec-journal entry.

**Parsing is fence-aware.** `_locate_section` (`fr/requirements.py:148`) ends
a section at the first line starting `## `, even inside a code fence. A spec
that shows a spec skeleton in a fenced example, as the 2026-09-28 spec does
at its line 131, would end `## Design` early. The Design parser skips lines
inside ```` ``` ```` / `~~~` fences when it looks for both the closing `## `
and the `### ` subsections.

Whether a behaviour is user-visible, and whether its backing really backs
it, stays reviewer judgement. The inventory makes the account complete and
visible, not correct, as the coverage partition did for coverage.

### C. The `fidelity` derived evidence on spec-review (R3)

`plugins/super-fr/workflows/fr-goal.yaml`'s `spec-review` step gains a
derived evidence name, `fidelity`, beside `coverage`. It is wired like
`coverage` in `packages/fr/src/fr/commands/run_cmd.py`: it joins
`_REQUIREMENTS_EVIDENCE` and the derived-name set, and its witness reads the
same review entry. It runs the two checks of §A and §B from a new module,
`packages/fr/src/fr/fidelity.py` (`check_fidelity`, `check_inventory`,
`parse_design_sections`). `fr/requirements.py` is already 629 lines and owns
the requirements grammar; this module consumes it (`parse_requirements`,
`coverage_block`) and is not imported by it.

It records `<c> clauses over <r> requirements (kept=<k> flagged=<f>);
<s> sections, <b> behaviours (invented=<i>)`. On a refusal it prints each
problem and the existing re-dispatch line (`_REDISPATCH`): the orchestrator
sends fr's message to the reviewer verbatim and records the new return, never
re-cutting a block itself.

A spec edited after the review (a removed behaviour, a restored clause) is
checked as it stands at resolve. An edit that renames or deletes a Design
section, or changes a reviewed requirement's quotes, is therefore refused
until the reviewer re-returns the blocks. That costs a re-dispatch, but it is
the only way the account stays true of the spec that ships.

### D. Invented and reinterpreted findings are removed, not confirmed (R4)

A finding named by a flagged `requirement-fidelity` row or an `invented`
`design-inventory` row closes only as `fixed` (the departure removed: the
invented behaviour deleted from the spec, or the requirement text restored to
its quote's clause) or `refuted` (the reviewer was wrong, with the reasoning
in the resolution body). The `fidelity` witness refuses spec-review while any
of them is closed any other way (`out-of-scope`, `deferred`, `unconfirmed`),
naming the finding and its `fr journal resolve … --state fixed` line.

`unconfirmed` is retired for new writes. `fr journal resolve --state
unconfirmed` (`commands/journal_cmd.py:420`) and a record's `state:
unconfirmed` (`record/apply.py`, `unconfirmed_refusal`) are refused with a
message citing d1-remove-only. The state stays in `RESOLUTION_STATES`, in
`ResolutionState` and in the journal fold, so an existing journal or record
that carries it still parses and still renders. This retires the state by
refusing writes, not by removing it from the schema, so no artifact changes
shape.

### E. Delegated decisions (R5, R6)

A `decision` journal entry may carry `delegated=true`: the operator answered
"Your call." (or chose to leave it to fr), and fr chose. The entry's body
records what was chosen and why.

- `JournalEntry.delegated: bool = False` (`fr/journal/model.py`): header
  token `delegated=true`, serialized only when set, valid only on a
  spec-scope `decision`. It is carried like `input=true`, so an older fr
  ignores the token and reads a plain decision; no journal bump.
- `JournalItem.delegated` in the step record (`fr/record/model.py`), which is
  `extra="forbid"`. This is a record shape change: the stamp moves 4 → 5 with
  a stamp-only migration, `fr.artifacts.record_delegated`, following
  `record_input_unconfirmed`.
- `fr journal add --delegated` for the verb path.
- A delegated decision is a valid `decision <id>` source and a valid
  inventory backing.

### F. PR body (R6, R7)

In `packages/fr/src/fr/record/pr_body.py`:

- **`## Built without operator confirmation`** now lists every delegated
  decision in the spec journal, with its title and the ids of the
  requirements whose `source` cites it, followed by any legacy `unconfirmed`
  finding the journal still carries, or `None.`.
- **`## Design inventory`** is new and joins `REQUIRED_SECTIONS` after
  `## Input coverage`. It renders the review's `design-inventory` table inside
  `<details>`, or, for a run whose spec-review recorded no `fidelity`
  evidence, `Not recorded (predates the fidelity gate).`. `deliver`'s
  existing live-PR check then refuses a PR missing it.

### G. Reviewer and skill prose (R1, R2, R4, R5)

- `plugins/super-fr/agents/fr-spec-reviewer.md`: "Faithful" becomes a
  clause-by-clause check with the `requirement-fidelity` block. "Nothing
  invented" becomes the `design-inventory` block. Both blocks join the
  return template. The resolution guidance for invented and reinterpreted
  findings reads "removed (or refuted), never confirmed" (d1).
- `plugins/super-fr/skills/fr-goal/SKILL.md` §2: invented and reinterpreted
  findings are resolved `fixed` by removal, no longer `unconfirmed`; the
  `fidelity` evidence joins `coverage` in the refusal list.
- `plugins/super-fr/skills/fr-brainstorming/SKILL.md` §1: a "Your call."
  answer is recorded as a decision with `delegated: true`.
- `packages/fr/src/fr/record/template.py`: the `unconfirmed` comment line is
  replaced, and the journal comment names `delegated: true` on a decision.
- The generated OpenCode and Hermes mirrors are regenerated by both sync
  scripts.

### H. Runs from before this gate

A run whose spec-review resolved before this change keeps its evidence as
recorded; nothing is re-derived. A run that predates the requirements gate
records the existing predates line for `fidelity` as for `coverage`. A run in
flight at spec-review is refused until its reviewer returns the two new
blocks, which fails closed.

### I. Docs and repo obligations

- `docs/explainers/01-fr-goal.md` names `unconfirmed` and the spec-review
  checks. It is updated and its `.html` is regenerated per
  `.claude/rules/explainers-currency.md`.
- A change fragment `.changes/feat-batch-spec-fidelity.yaml`, `bump: minor`
  (new mandatory review output, a new PR section).
- Acceptance rows per §Test Plan, in the brainstorm record.

## Non-goals

- Asking the operator at spec-review (d1).
- Machine-checking that a clause labelled `kept` really is kept, or that a
  behaviour is really user-visible. Both stay reviewer judgement; fr checks
  that the account is complete.
- Relaying requirement quotes to phase executors (the operator-input relay is
  super-fr#778's).
- Removing `unconfirmed` from any schema.

## Test Plan

1. **Clause partition (R1, R3).** Unit tests on `check_fidelity`: a sound
   block passes; a missing requirement, a skipped or reordered clause, a
   clause crossing an elision, an unknown finding id, and a decision-only
   requirement given rows are each refused; a requirement added after the
   review (absent from `input-coverage`) is not demanded.
2. **Design inventory (R2, R3).** Unit tests on `parse_design_sections` and
   `check_inventory`: fenced `## ` / `### ` lines ignored; a Design without
   subsections is one section `Design`; a missing, reordered or unknown
   section, an unknown `R`/decision id, an `invented` id that is not a
   finding, and a `none` backing beside a real behaviour are each refused.
3. **Evidence wiring (R3, R4).** `fr run resolve --step spec-review` with a
   record: refused without the blocks, refused while an invented or
   reinterpreted finding is closed other than `fixed`/`refuted`, passes and
   records the counts line when sound.
4. **`unconfirmed` retired (R4).** `fr journal resolve --state unconfirmed`
   and a record `state: unconfirmed` are refused; an existing journal with an
   `unconfirmed` record still folds and renders.
5. **Delegated (R5).** Journal round-trip of `delegated=true`; refused on a
   non-decision; record 4 → 5 migration; `fr journal add --delegated`.
6. **PR body (R6, R7).** `## Built without operator confirmation` lists
   delegated decisions with their citing requirements; `## Design inventory`
   renders the table, or the predates line; `missing_sections` requires it.
7. **Live (R2), post-merge.** Take 10's fr arm, run with this change on the
   feature-C brief, produces a spec-review with an `invented` finding for any
   card-click toggle the spec carries, and the delivered spec has none.
