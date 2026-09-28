# Requirements traceability: the spec captures what was asked, and fr checks the capture

**Status:** design · **Date:** 2026-09-28 · **Closes:** super-fr#759
**Builds on:** `docs/superpowers/implemented/specs/2026-09-24-fr-goal-scope-proportion-cost-design.md`
(dispatched `fr-spec-reviewer`, gh#593; finding scope tags, gh#597),
`docs/superpowers/implemented/specs/2026-09-26-dynamic-brainstorm-question-rounds-design.md`
(the question round)

## Background

fr-goal is rigorous about "did we do what we planned" and has nothing that asks
"did we plan what was asked". The operator's input is paraphrased once, into the
spec, and every later stage (`fr-spec-reviewer`, the phase executor,
`review-phase`, `deliver`) works from that paraphrase. #759 documents one run
where the spec:

- **invented** user-visible behaviour ("cards toggle membership": the input
  said nothing about card clicks);
- **reinterpreted** a stated range ("1–20" became a lower bound on the − control,
  so a quantity could not reach 0);
- **dropped** a stated constraint ("no unstyled browser defaults").

The implementation then built the spec faithfully, including all three. A
single-context agent given the same input met every criterion. Across repeated
runs the divergence clusters at input → spec.

The issue proposed carrying the brief verbatim to every executor and reviewer.
Its follow-up comment, and the operator, rejected that as the main fix. The
input has no quality control: it can be one line from a client or a
spec-shaped analyst document, and brainstorming may depart from it for good
reason. Handing noisy input downstream as "the source of truth" would compete
with the spec and confuse the agents that read both. **The spec is the
requirements carrier**, and the defect is that nothing checks the capture.
Plain `superpowers:brainstorming` gets this right by asking; fr-goal's automated
brainstorm decided those calls itself.

## Decisions (operator, 2026-09-28)

| id | decision |
|---|---|
| d0-spec-is-the-carrier | The raw input is NOT carried to executors or reviewers downstream (issue proposals 1 and 5 are dropped). Improve spec creation and spec review instead; the spec, once checked, is what everything downstream reads. |
| d1-input-in-spec-journal | The raw input is preserved verbatim as an entry in the **spec journal**, which `fr-spec-reviewer` already reads and executors never receive (they get `fr journal handoff --scope plan`). |
| d2-always-ask | Every user-visible behaviour the spec needs that no input statement asks for, and every interpretation of an ambiguous input statement, becomes a question in the brainstorm round. There is no "assumption" escape at brainstorm time. |
| d3-late-unconfirmed | An invented or reinterpreted behaviour that spec-review finds AFTER the round closed does not reopen the gate: it is kept, resolved `unconfirmed`, and listed in the PR body for the operator to veto at merge. |
| d4-structural-gate | fr machine-checks the Requirements section's form and sources (derived evidence); coverage ("was anything dropped?") stays reviewer judgement. |
| d5-rows-gate-deliver | Every requirement is cited by ≥1 acceptance row; `deliver` refuses while any row citing the run's spec is `not-implemented`. |
| d6-approach-a | Requirements live in a `## Requirements` section of the spec with a fixed grammar, parsed by a new `fr/requirements.py` (not a YAML sidecar, not front matter). |
| d7-requirements-table | Requirements (and Deferred from input) are Markdown tables, in the same form as `## Decisions`, not lists. |
| d8-spec-review-hard | `spec-review` runs at the `hard` tier. It is the one point where the input is consulted again, and the drift it must catch is produced fluently by a strong author; a weaker reviewer is the wrong economy there. |
| d9-coverage-partition | Spec review returns an input-coverage table that partitions ALL of the input text into spans labelled `R<n>` / `deferred` / `context` / `missing <finding>`; fr verifies the partition, so a skimmed input is a refusal rather than an invisible miss. |
| d10-traceability-first | fr-spec-reviewer runs the traceability check FIRST, before the codebase lookups that otherwise consume its attention. |
| d11-post-merge-rows | A matrix row may declare `verify: post-merge`. `deliver`'s row gate skips it; the PR body lists it as owed post-merge verification. The row stays `not-implemented`, visibly owed, rather than being relabelled `skipped` (which claims verification exists). |
| d12-coverage-in-pr | The coverage table is rendered in the PR body. It was part of the option the operator selected for d9 ("Rendered in the PR body") but missing from d9's journal entry; spec-review finding r7 caught the gap. |
| d13-paraphrase-cell | The Requirements table's `requirement` cell is fr's capture in its own words; fidelity rests on the verbatim `source` quote beside it and on spec review's "faithful" check. The input's "Paraphrase only in the design sections" is deferred, citing this decision. |

Out of scope, filed as super-fr#760: the issue comment's item 1, fr-plan's
"prefer 4–6 phases" versus "one agentic phase is first-class" contradiction.

## Requirements

| id | requirement | source |
|---|---|---|
| R1 | The operator's raw input is preserved verbatim where spec review can trace against it, and is not dispatched to executors or phase reviewers. | decision d0-spec-is-the-carrier<br>decision d1-input-in-spec-journal |
| R2 | The spec separates requirements (each traced to a source: the raw input or an answered question) from fr's own design decisions. | input "Split the spec into Requirements and Design."<br>input "Quote acceptance criteria verbatim in the spec" |
| R3 | User-visible behaviour the input does not ask for, and the interpretation of any input statement with more than one reasonable reading, is asked in the question round, never silently promoted to a requirement. | input "never silently promoted"<br>decision d2-always-ask |
| R4 | Spec review traces the spec back to the raw input: every input statement is covered or explicitly deferred, every requirement has a source, and invented or reinterpreted behaviour is a finding, in scope by default. | input "Spec review traces Requirements back to the raw input,"<br>input "each input statement is covered or explicitly deferred; every requirement has a source."<br>input "are in scope by default." |
| R5 | Behaviour spec-review flags after the round closed is kept and listed in the PR body as built without operator confirmation. | decision d3-late-unconfirmed |
| R6 | fr refuses a spec whose requirements are malformed, unsourced, or quote text the input does not contain. | decision d4-structural-gate<br>decision d7-requirements-table |
| R7 | Acceptance rows are seeded from the requirements, and `deliver` cannot pass while one is unevidenced. | input "Seed acceptance rows from Requirements,"<br>decision d5-rows-gate-deliver |
| R8 | Spec review accounts for every part of the input, fr refuses a review that leaves any of it unclassified, and the PR shows the classification. | decision d9-coverage-partition<br>decision d12-coverage-in-pr |
| R9 | Spec review runs on the strongest reviewing tier and checks traceability before anything else. | decision d8-spec-review-hard<br>decision d10-traceability-first |
| R10 | A requirement that can only be verified after merge does not block delivery, and stays visibly owed. | decision d11-post-merge-rows |

## Deferred from input

| input | reason |
|---|---|
| "Pass it in every executor and reviewer dispatch as **the source of truth**" | Rejected by d0-spec-is-the-carrier. |
| "Review phases against the brief's criteria too" | Rejected by d0-spec-is-the-carrier; review-phase keeps reviewing against the (now checked) spec. |
| "fewer, larger phases make the plan lossier" | Corrected by the issue's own comment; the fr-plan guidance contradiction is super-fr#760. |
| "Worth reconciling there." | Filed as super-fr#760; not this change. |
| "Store it as a run artifact at `start`" | Replaced by d1-input-in-spec-journal: recorded in the spec journal at brainstorm, not as a run artifact at start. |
| "Seed the acceptance matrix from the brief's criteria, word for word." | Superseded by the comment's "Seed acceptance rows from Requirements,": rows are seeded from requirements, whose sources quote the input verbatim (R7). |
| "The rows shouldn't be only the run's own restatements." | Met through R7's rows citing requirements whose `source` quotes the input verbatim; a row's own text is not required to be a quote. |
| "Paraphrase only in the design sections." | Superseded by d13-paraphrase-cell. |

## Design

### A. The raw input in the spec journal (R1)

Brainstorm writes the operator's input, verbatim, as a spec-journal entry of
kind `discovery` carrying a new header token `input=true`: the goal text as
typed, or the issue's title and body (plus any comments the operator points
at). A spec may have several input entries (an issue plus a clarifying message).

The token copies the `out_of_scope=true` mechanism
(`packages/fr/src/fr/journal/model.py:43-49`, `:112`): serialized only when set,
projected by name in `parse_journal`, so an older `fr` drops it and reads a
plain `discovery`. No journal stamp bump.

Writers:

- the brainstorm step record: `journal: [{kind: discovery, input: true, id, title, body}]`;
- with no run: `fr journal add --scope spec --kind discovery --input …`.

`input` is refused on any kind other than `discovery` and on any scope other
than `spec`. The rule lives in the `JournalEntry` model validator, beside
`out_of_scope`'s (`packages/fr/src/fr/journal/model.py:157-161`), so the verb
(`--input`) and the record path (`JournalItem.input`) share one check (review
r4).

**Redaction at capture (review o6).** "Verbatim" is verbatim after
`.claude/rules/third-party-privacy.md`'s redaction: an input that names a
third-party host, org, repo or person is redacted when the entry is written
(RFC 2606 names, keeping the shape), and the entry's body says that it was
("host redacted"). Quotes and the coverage partition then match the redacted
text, which is the only text ever committed. The rule is a consumer-repo
concern too: the skill prose tells the orchestrator to redact before writing,
because nothing downstream can redact a journal without breaking every quote.

Nothing else changes about who reads the spec journal: `fr-spec-reviewer`
already does; `fr journal handoff --scope plan` (the executor's context) never
includes it.

### B. The spec's Requirements grammar (R2, R6)

A spec written by fr-brainstorming carries, before `## Design`, two tables in
the same form as `## Decisions` (d7-requirements-table):

```markdown
## Requirements

| id | requirement | source |
|---|---|---|
| R1 | <one requirement, one line> | input "<verbatim quote>"<br>decision <journal decision id> |

## Deferred from input            (optional)

| input | reason |
|---|---|
| "<verbatim quote>" | <one-line reason it is not a requirement of this change> |
```

Parse rules (`fr.requirements.parse_requirements`, pure, no I/O):

- Each section holds exactly one GitHub-flavoured Markdown table and nothing
  else but blank lines. Its header row is exactly the column names above
  (case-insensitive, surrounding spaces ignored), followed by a delimiter row.
  Any other content in the section (a paragraph, a second table, a list) is a
  parse error, never skipped.
- Cells split on unescaped `|`. A `|` inside a quote or requirement is written
  `\|` and unescaped before matching; a row with the wrong cell count is an
  error.
- `id` is `R` + a positive integer, unique within the spec, not required to be
  contiguous (so a deleted requirement never renumbers the rest and breaks row
  citations). `requirement` is non-empty.
- `source` holds one or more sources separated by `<br>`, each either
  `input "<quote>"` (the quote runs from the first `"` to the last `"` of that
  source) or `decision <id>`. An empty cell or an unknown form is an error.
  Deferred's `input` cell is one `"<quote>"`; its `reason` is non-empty.
- A quote may contain ` … ` (U+2026 with a space on each side) to elide: each
  fragment must occur in the input entry, in order. An input that itself
  contains ` … ` needs nothing special: quoting across it splits there too, and
  both fragments still occur in order.
- Quote matching normalises whitespace only: runs of whitespace (newlines
  included) collapse to one space, ends stripped. Case, punctuation and dashes
  are literal: "1–20" does not match "1-20". A quote must fall within a single
  input entry.

`## Design` holds fr's own decisions. The gate does not parse it: whether it
smuggles in user-visible behaviour is judgement (§D).

### C. The `requirements` derived evidence (R6, R7)

`fr.requirements.check_requirements(spec_text, journal_entries, matrix, spec_ref)
-> list[str]` returns the problems, empty when sound:

1. at least one input entry (§A) in the spec journal;
2. the Requirements section exists and parses (§B), with at least one item;
3. every `input` quote (Requirements and Deferred) matches an input entry;
4. every `decision` id names a `kind=decision` entry in the spec journal;
5. every requirement id is cited by at least one matrix row origin of the form
   `<repo>:<spec-path>#R<n>` (one row may cite several). Resolution reuses the
   matrix's existing twin-aware ref handling, so a citation survives
   `fr archive`.

`requirements` joins `_DERIVED_EVIDENCE` / `_VERIFIABLE_EVIDENCE` /
`_DERIVED_FROM` (`packages/fr/src/fr/commands/run_cmd.py:1381-1395`). It is
never passed (`--evidence requirements=` is refused like `findings=`). On
resolve `done`, fr runs the check against the run's spec and the spec journal
(on `brainstorm`'s own resolve that is the spec in THIS resolve's emitted map,
`--emitted spec=` or the record's `emitted:`, since the cursor holds none yet;
on `spec-review` it is `brainstorm`'s stored `emitted.spec`, review r6), refuses with every problem listed, and
otherwise records `<n> requirements:<sha256 of the normalised section>`.

The manifest (`plugins/super-fr/workflows/fr-goal.yaml`) declares it on
`brainstorm` (`evidence: [requirements]`) and on `spec-review` (appended, with
§D's `coverage`, to `[review, reviewer, findings]`): spec-review's fixes edit the
spec, so it is re-derived there. `spec-review` also gains `acceptance` in its
`emits` (review o2): fixing a dropped finding adds a requirement, and the
requirement's row must ride the same record, or the re-derived gate refuses the
fix it asked for. Drift compares step ids only, so no addition strands a
cursor.

All three new names, `requirements`, `coverage` and `requirement-rows`, join
`_VERIFIABLE_EVIDENCE`, `_DERIVED_EVIDENCE` and `_DERIVED_FROM` (reviews o1,
r5): the resolve path refuses a declared name missing from the first
(`run_cmd.py:1593`), and one missing from the second would be demanded as
`--evidence <name>=`.

When the record also carries the acceptance rows (brainstorm emits
`acceptance`), the check runs against the matrix as the record will leave it:
it executes inside `apply_record`'s in-memory build, after the rows are staged.

**Standalone:** `fr spec requirements <spec> [--journal <path>]` runs the same
function and exits 2 on any problem (0 and a one-line summary otherwise). It is
what a brainstorm without a cursor uses, and it is the only implementation:
both gates call `check_requirements`, never a copy.

### D. Spec review: traceability first (R4, R5, R8, R9)

`plugins/super-fr/agents/fr-spec-reviewer.md` gains a check, **Traceability to
the input**, named in its front-matter `description:` and in its "things, in
this order" heading as well as its body (review r9: #759 quotes that
description as the defect), and runs it FIRST, before its existing three (decisions, codebase
reality, internal consistency), so the codebase lookups cannot crowd it out
(d10). It reads the input entries from the spec journal it is already given:

- **Covered or deferred.** Every statement of the input maps to a requirement,
  or appears under `## Deferred from input`. A statement in neither is a
  **dropped** finding.
- **Faithful.** A requirement says no more and no less than its quotes; a
  narrowed or widened range, an added condition, or a changed default is a
  **reinterpreted** finding.
- **Nothing invented.** User-visible behaviour in `## Design` (or anywhere
  outside Requirements) with no requirement behind it is an **invented**
  finding.

All three are tagged in scope. The reviewer says, per finding, which
resolution it expects:

- **dropped** → fix: add the requirement (and its row), or defer it
  explicitly with a reason. No operator needed: the input already decided it.
- **invented / reinterpreted** → the operator was never asked, and the gate is
  closed (d3). The orchestrator resolves it `unconfirmed` with a note stating
  what will be built, OR removes the behaviour when the literal reading of the
  input suffices. It must not rewrite the requirement to match the design.

**The `unconfirmed` resolution.** `fr journal resolve … --state unconfirmed
--note "<what gets built>"` appends an `open` resolution record with header
token `unconfirmed=true`, exactly as `out-of-scope` is carried. The fold's
`EffectiveFindingState` gains `unconfirmed`; the spec-review `findings` gate and
`fr journal check` treat it as closed. An older `fr` drops the token and reads
the finding as open: fail closed, no journal bump. `unconfirmed` is refused on a
finding whose `review_scope` is `out`, and on a plan-scope finding (it is a
spec-capture state).

Resolution state is gated in THREE places today, and all three move together
(review finding s1):

1. the verb: `RESOLUTION_STATES` in `packages/fr/src/fr/commands/journal_cmd.py:297`
   (checked at `:366`) gains `unconfirmed`; the `review_scope == "out"` and
   `--scope plan` refusals run in `resolve()` after the target finding is
   loaded (`:396`);
2. the record path: `_journal_writes` in `packages/fr/src/fr/record/apply.py:352-374`
   maps `unconfirmed` like `out-of-scope` (`state="open"` at `:363`, the
   `unconfirmed=True` token beside `out_of_scope=` at `:366`), and applies the
   same two refusals, reading the step's journal scope from the manifest since
   a flat `Resolution` carries no `--scope`;
3. the model: `ResolutionState` in `packages/fr/src/fr/record/model.py:60`
   (§H's record bump).

**The input-coverage partition (d9).** Spec review returns, inside the body of
its `kind: review` journal entry (the entry `evidence.review` already names), a
fenced table that partitions the input:

````markdown
```input-coverage
| span | coverage |
|---|---|
| "<verbatim span of the input>" | R1, R4 |
| "<next span>" | context |
| "<next span>" | deferred |
| "<next span>" | missing s3 |
```
````

`coverage` is one of: one or more requirement ids (comma-separated);
`deferred`; `context` (narrative, evidence, rationale, i.e. not a requirement);
`missing <finding-id>`. Cell escaping follows §B. A span is literal: `…` in a
span is the input's own character, never an elision (review r3: #759's own
input contains ` … `, so an elision token would make it unpartitionable). A
span that skips text is refused by check 2 below, which needs no special token.

A new derived evidence, `coverage`, on `spec-review` verifies it at resolve
(`fr.requirements.check_coverage`):

1. the review entry named by `evidence.review` contains exactly one
   `input-coverage` block, and it parses;
2. the spans concatenated in table order EQUAL the input entries' bodies
   concatenated in journal order, compared with ALL whitespace removed on both
   sides: a partition, with no gap, overlap or reordering. Whitespace-insensitive
   rather than whitespace-normalised, because a boundary may fall on whitespace
   (lost when the cell is trimmed) or on none (a cut right after `)`), and no
   single join rebuilds both (phase 1 review finding c1);
3. every requirement id exists in the spec's Requirements table as it stands at
   resolve;
4. every `missing <id>` names a `kind=finding` entry in the spec journal. The
   existing `findings` gate then holds the resolve until that finding is closed.

It records `<n> spans: R=<a> deferred=<b> context=<c> missing=<d>`. Whether a
span is labelled correctly (above all, something mislabelled `context`) stays
the reviewer's judgement. The partition makes the labelling complete and
visible, not correct.

**Tier (d8).** `fr-goal.yaml`'s `spec-review` moves from `tier: standard` to
`tier: hard`. A tier is not a step id, so no cursor drifts.

**PR body.** `packages/fr/src/fr/record/pr_body.py` adds
`## Built without operator confirmation` to `REQUIRED_SECTIONS`, after
`## Out-of-scope findings`: every `unconfirmed` spec finding with its note (the
body of the `unconfirmed` resolution record, not the finding's own body), or
`None.`. `unconfirmed` joins `_CLOSED_OUT`'s partition as a third bucket
(`pr_body.py:50`, `:86-98`), so such a finding renders in this section only,
never also under `## Findings` (reviews o7, r8). `deliver` already refuses a live PR missing a required section, so this
list cannot be left out.

It also adds `## Input coverage` to `REQUIRED_SECTIONS` (d12), after the
unconfirmed section: the spec-review coverage table inside `<details>` (it can be long),
or `Not recorded (predates the requirements gate).` for a run §G covers.

### E. Brainstorm prose: always ask (R3)

`plugins/super-fr/skills/fr-brainstorming/SKILL.md` and fr-goal §1 add:

1. Record the input first (§A), before exploring.
2. Before the round: list every user-visible behaviour the design needs, and
   every input statement with more than one reasonable reading. Each one no
   input statement settles is a question in the round, whose answer becomes a
   `decision` a requirement can cite. fr-goal's existing "past ~10 questions,
   say why or propose splitting the goal" guard is the pressure valve; there is
   no assumption list.
3. Write the spec in the §B shape: Requirements (quotes verbatim, paraphrase
   only in the requirement's text), Deferred from input, then Design.
4. One acceptance row per requirement or group of requirements, origin
   `<repo>:<spec>#R<n>`.

fr-goal §2 gains the `unconfirmed` path; §8 names `requirement-rows`.
`fr-acceptance` documents the `#R<n>` origin form.

### F. The `requirement-rows` derived evidence on `deliver` (R7)

`deliver` gains `requirement-rows` (derived): its manifest entry becomes
`evidence: [tests, proportionality, requirement-rows]`. On `done`, fr collects
every matrix row with an origin naming the run's spec path (any fragment or
none) and refuses while any is `not-implemented`, naming each row and the
`fr acceptance set-status` line that moves it. `skipped` passes: verification
exists but is not in CI, which the SessionStart nag already reports as debt.
`deliver` emits `acceptance`, so rows its own record moves are counted as the
record leaves them (the staged matrix, as §C does for `brainstorm`).

**Post-merge rows (d11).** A row declaring `verify: post-merge` is skipped by
this gate whatever its status. It is the honest home for a requirement only a
live, operator-driven run can prove (this spec's R3 and R4 rows): it stays
`not-implemented`, keeps nagging in `fr acceptance status`, and the PR body
lists it under a new required section, `## Post-merge verification owed`
(each row id and its acceptance line, or `None.`). Writers: `fr acceptance add
--verify post-merge`, `verify: post-merge` on a record's `acceptance:` item,
and `fr acceptance set-status --verify post-merge` (phase 4 review finding
g2: rows created before they were known to be live-only must be markable
without a delete verb — `add` is create-only and matrix.yaml is never
hand-edited). `set-status` preserves the row's existing `verify` unless
`--verify post-merge` is given; moving the row off `not-implemented` after the
live run is the ordinary transition and needs no `--verify`.

It records `<n> rows: <status>=<count>,…; post-merge=<m>`.

### G. Runs from before this gate

If `brainstorm`'s step record carries no `requirements` evidence (resolved by an
older `fr`, or rebuilt by `fr run adopt`), each of `requirements` (on
`spec-review`), `coverage` and `requirement-rows` records `predates the
requirements gate` instead of refusing, independently, and `fr run status`
shows it as `done, unevidenced`, the same treatment `review-phase` got. Nothing in
flight is stranded, and nothing is retroactively failed.

### H. Artifact versioning

| kind | moves | why |
|---|---|---|
| journal (1) | no | `input` and `unconfirmed` are header tokens; older readers drop them and fail closed. |
| record (2) | **2 → 3** | `JournalItem.input: bool = False`, `AcceptanceItem.verify: Literal["post-merge"] \| None = None` and `ResolutionState` + `"unconfirmed"` on an `extra="forbid"` model (`packages/fr/src/fr/record/model.py:60,71,98,136`). A stamp-only `SchemaMigration`, registered next to `fr.artifacts.record_questions`. No field is removed or moved, so no frozen legacy model is owed. |
| run (7) | no | `StepRecord.evidence` is `dict[str, str]`; new evidence names are values. |
| spec (1) | no | The grammar is enforced by the run gate and `fr spec requirements`, not by `fr validate artifacts`; historic specs stay valid and none is rewritten. |
| matrix (1) | **1 → 2** | `Row.verify: Literal["post-merge"] \| None = None` on an `extra="forbid"` row (`packages/fr/src/fr/acceptance/model.py:55-67`), so an older `fr` would reject a row carrying it. This is the first time the matrix kind moves past 1, so `Matrix` gains `schema_version: int = 1` in the same PR (artifact-versioning rule). A stamp-only `SchemaMigration`; no field is removed. `#fragment` refs need nothing (`:36`). |

The record and matrix bumps each ship their migration and validator update,
and `fr migrate artifacts --yes` runs over this repo's own records and
`docs/acceptance/matrix.yaml` in the same PR. The chain test asserts each hop
(`[2, 3]` for record, `[2]` for matrix).

### I. Docs and repo obligations

- A `minor` change fragment.
- `docs/explainers/01-fr-goal.md` gains the requirements capture and the two
  gates; its `.html` is regenerated per `explainers-currency.md`.
- AGENTS.md: a pointer for `fr/requirements.py`.
- Both mirror generators (`scripts/sync-opencode.py`, `scripts/sync-hermes.py`)
  after the skill and agent edits; all prose passes the tool-neutrality
  tripwire.

## Non-goals

- Carrying the raw input to executors, `review-phase` reviewers, or any
  dispatch brief (d0).
- An "assumptions" list at brainstorm time (d2).
- Reopening the operator gate at spec-review (d3).
- Machine-checking the CORRECTNESS of coverage labels or Design content: both
  remain reviewer judgement (d4). fr checks that the coverage partition is
  complete (d9), not that each label is right.
- A second, dedicated traceability reviewer: d10's ordering and d9's partition
  buy most of its focus without another dispatch and gate.
- Tagging plan phases or steps with requirement ids.
- Reconciling fr-plan's phase-count guidance (super-fr#760).

## Test Plan

Unit (CI):

1. `parse_requirements`: a well-formed table; `<br>`-separated sources; an
   escaped `\|` in a quote; an empty source cell; a wrong cell count; a wrong
   header; a malformed id; a duplicate id; a stray paragraph beside the table;
   an unknown source form; a missing section; an empty Deferred `reason`. Each
   malformed case is a named error.
2. Quote matching: whitespace and newline normalisation matches; `1–20` does
   not match `1-20`; ` … ` fragments must occur in order; a quote spanning two
   input entries is refused; Deferred quotes are checked too.
3. `check_requirements`: no input entry; an unknown decision id; an id naming a
   non-decision entry; an uncited requirement; a row citing two requirements
   covers both; a citation to an archived spec twin resolves.
4. **#759 replay, deterministic half:** a generic fixture built from the
   issue's quoted input lines. A spec whose R1 quotes "(1–20)" passes; one
   quoting text absent from the input is refused; a spec that drops the
   "no unstyled browser defaults" line from both Requirements and Deferred
   **passes** the structural gate. That pins coverage as reviewer territory.
5. `fr run resolve --step brainstorm` refuses each §C problem and records
   `<n> requirements:<sha>`; `--evidence requirements=` is refused; rows staged
   in the same record count as citations; the spec is found from this
   resolve's own `emitted` (record form and `--emitted` form).
6. `spec-review` re-derives `requirements` after the spec changes (new hash); a
   spec-review record that adds a requirement AND its row in `acceptance:`
   applies.
7. `deliver`: refuses with a `not-implemented` row citing the spec, naming the
   `set-status` line; passes on `skipped` / `ci` / `scheduled`; skips a
   `verify: post-merge` row and counts it; counts a row the deliver record
   itself moves as moved; records counts.
8. A run whose brainstorm evidence lacks `requirements` records
   `predates the requirements gate` for `requirements`, `coverage` and
   `requirement-rows`, and `fr run status` renders it `done, unevidenced`.
9. Journal: `input=true` and `unconfirmed=true` round-trip; a parse that ignores
   both tokens reads a discovery and an open finding; the fold yields
   `unconfirmed`; `fr journal check` and the `findings` gate treat it as closed;
   `input` on a non-discovery kind or a non-spec scope, and `unconfirmed` on an
   `out` or plan-scope finding, are refused on BOTH the verb and the record
   path (`apply.py`), each exercised separately. A redacted input entry passes
   the quote check against its redacted text.
10. Record 2 → 3 and matrix 1 → 2: each hop asserted; a record carrying `input`,
    `verify: post-merge` and an `unconfirmed` resolution applies; a v2 record and
    a v1 matrix still migrate and apply; `Matrix` accepts `schema_version`.
11. PR body: `## Built without operator confirmation` (the resolution notes, or
    `None.`), `## Input coverage` (the table, or the predates line) and
    `## Post-merge verification owed` (rows, or `None.`) are rendered and in
    `REQUIRED_SECTIONS`; a live body missing any is refused; an `unconfirmed`
    finding is absent from `## Findings`.
12. `check_coverage`: an exact partition passes and records its counts,
    including an input containing ` … ` partitioned literally (the #759 input
    itself, redacted fixture); a gap (a span that skips text), an overlap, a
    reordered span, a second block, no block, an unknown requirement id, and
    `missing <id>` naming no finding are each refused; a `missing` finding still open holds the resolve through the
    existing `findings` gate; `--evidence coverage=` is refused.
13. `fr spec requirements` exits 0 and 2 on the fixtures of 1–3.
14. The shipped `fr-goal.yaml` passes `fr workflow check`, its `spec-review` is
    `tier: hard`, and an in-flight cursor does not drift.
15. fr-spec-reviewer's prose orders traceability before the other checks and
    its `description:` names it (a text pin on the agent file).
16. Mirrors in sync (OpenCode skills, agents, instructions; Hermes skills);
    tool-neutrality tripwire green.

Post-merge (operator-driven):

17. One live `/fr-goal` on a small UI brief that leaves card interactions and a
    range's edge behaviour unstated. The round asks about each; the spec's
    requirements quote the brief verbatim and cite the answers; `deliver`
    refuses until the rows move off `not-implemented`.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-28-requirements-traceability | `derio-net/super-fr` | `2026-09-28-requirements-traceability` | — |
