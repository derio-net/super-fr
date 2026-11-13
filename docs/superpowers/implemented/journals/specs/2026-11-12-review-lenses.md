<!-- fr:journal-schema=4 -->
# Journal: 2026-11-12-review-lenses

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-12T15:54:50+00:00 input=true -->
### brief · discovery · Operator's brief, verbatim

How can we ship better code with super-fr? How can we sensibly use flows or steps in the existing flows to make the code more maintainable, readable, secure? An extra datapoint: https://evanxmerz.com/post/ai-usage-generates-a-fragile-codebase/

<!-- fr:journal kind=decision scope=spec id=d1-first-focus created=2026-11-12T15:54:50+00:00 decided_by=operator -->
### d1-first-focus · decision · Design review lenses first

Asked which of four quality areas to design first (review lenses, whole-change review, reuse search at plan time, operator comprehension). Operator chose review lenses. The other three are later specs.

<!-- fr:journal kind=decision scope=spec id=d2-lenses-per-phase created=2026-11-12T15:54:50+00:00 decided_by=operator -->
### d2-lenses-per-phase · decision · Lenses are chosen per phase in the plan

Asked how lenses are applied in a phase's review. Operator chose lenses named on the plan's phase header, checked by fr plan self-review, with one reviewer covering the named ones; not all lenses always, not one reviewer per lens.

<!-- fr:journal kind=decision scope=spec id=d3-waiver-plus-path-rules created=2026-11-12T15:54:50+00:00 decided_by=operator -->
### d3-waiver-plus-path-rules · decision · Every lens applied or waived with a reason, plus repo path rules

Asked what stops a phase under-declaring. Operator chose both: every agentic phase states each lens as applied or waived with a reason, and a repo may map path globs to mandatory lenses that a waiver does not satisfy.

<!-- fr:journal kind=decision scope=spec id=d4-four-shipped-repo-may-add created=2026-11-12T15:54:50+00:00 decided_by=operator -->
### d4-four-shipped-repo-may-add · decision · Four shipped lenses; a repo may add, replace and disable

Asked which lenses exist. Operator chose security, tests, simplicity and errors shipped by fr, with a repo file able to add lenses or replace a shipped lens's instruction text.

<!-- fr:journal kind=decision scope=spec id=d5-evidence-tied-to-files created=2026-11-12T15:54:50+00:00 decided_by=operator -->
### d5-evidence-tied-to-files · decision · Reviewer lines tied to changed files, checked by fr, shown in the PR

Asked what the reviewer returns per lens. Operator chose one line per declared lens naming changed files examined and finding ids; fr refuses the review resolve on a missing line, no file from the phase's diff, or an unknown finding id; the result is stored on the run and shown as a table in the PR body.

<!-- fr:journal kind=decision scope=spec id=d6-verification-candidate created=2026-11-12T15:54:50+00:00 decided_by=operator -->
### d6-verification-candidate · decision · Verified on a candidate build, all rows, no post-merge walk

The standing verification question. Operator chose the candidate strategy for every row, with a stubbed reviewer return in the scenarios; no gate holds the close-out.

<!-- fr:journal kind=decision scope=spec id=d7-feature-level-review created=2026-11-12T16:44:48+00:00 decided_by=operator -->
### d7-feature-level-review · decision · Lenses are reviewed once, at feature level before deliver; supersedes d2 and d3

The operator asked whether concrete lenses would limit the phase reviewer's autonomy, then proposed a separate feature-level review before deliver that looks for the chosen lenses, with any agent able to add a lens at any step and the lenses accumulating. The per-phase review stays general. The usual in-scope fix and out-of-scope filing rules apply. This replaces per-phase lens declarations (d2) and waivers (d3); path rules are kept.

<!-- fr:journal kind=decision scope=spec id=d8-starting-set created=2026-11-12T16:45:19+00:00 -->
### d8-starting-set · decision · The lens set is agent additions plus path rules; an empty set is visible

Asked the operator, through the question tool, what the feature-level review starts from. They chose: whatever agents added plus every lens a repo path rule requires for the files actually changed; with an empty set no review is dispatched and the PR says no lens was requested. (Answered in the same session as d7; fr's operator-answer check matched that session's later answer to d7 only, so this entry carries no answered_by.)

<!-- fr:journal kind=decision scope=spec id=d9-one-reviewer-per-lens created=2026-11-12T16:45:23+00:00 -->
### d9-one-reviewer-per-lens · decision · One reviewer per accumulated lens

Asked the operator, through the question tool, how many reviewers the feature-level review dispatches. They chose one per lens, each given only its own lens and the whole feature diff. (Recorded without answered_by for the reason given in d8.)

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-11-12T17:13:17+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · `fr run advance` never completes a `kind: agent` step; §3.C assumes it does on an empty lens set

check: codebase
target: spec
evidence: spec §3.C "Advance" and R11; packages/fr/src/fr/commands/run_cmd.py:5820-5869 (the agent branch always briefs, opens a dispatch and returns "brief"); run_cmd.py:5871 (only `cli` executes); run_cmd.py:6918-6929 (resolve refuses a cli step); AGENTS.md (fr/run): "`advance` ... never a `kind: agent` one ... `resolve` is the only way an `agent` step's cursor moves past `running`"
scope: the spec introduces the auto-complete and depends on it
§3.C says that with an empty set `fr run advance` "completes the step itself ... as it does for a `cli` step". No path does this today, and it breaks a stated invariant of `fr/run`. The spec has to name the exception and design it, or keep advance unchanged and let the orchestrator resolve the step at once, with `lenses` derived as `none`. Either way, pick one and add a Verification scenario for it.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-11-12T17:13:17+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · The review/reviewer/findings verifiers refuse a flat step that emits journal:plan; "held as on a phase review" needs a new evidence target

check: codebase
target: spec
evidence: spec §3.C "Resolve"; run_cmd.py:1666-1694 (`_EvidenceTarget` is plan+phase or spec+None; `_evidence_target` returns None for a flat step whose emits lack journal:spec); run_cmd.py:1907-1916 (target None plus review/reviewer/findings: exit 2); run_cmd.py:3279-3290 (`_target_finding_states` with phase None takes EVERY finding in the journal); run_cmd.py:2069 and 2515-2578 (`_check_returned_findings` runs only when `target.phase` is set); run_cmd.py:3248-3276
scope: the spec's lens-review step cannot resolve without this
`lens-review` is flat and emits `journal:plan`. As the code stands, each of its three review obligations is refused before anything is checked. The spec must design a third target (plan journal, feature level) and route it through each consumer: the review-entry rule, a findings set limited to lens-review ids, and a returned-findings check that matches unphased ids.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-11-12T17:13:17+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · `reviewer` evidence holds one dispatch id; the lens review has one reviewer per lens

check: codebase
target: spec
evidence: spec §3.C "Resolve", R8, decision d9; run_cmd.py:1762-1766 (`--evidence reviewer=` given twice is refused); run_cmd.py:2397-2402 (`_verify_reviewer` checks one `agent_id`); run_cmd.py:2546-2563 (only the NAMED reviewer owes a block)
scope: per-lens coverage is this spec's core guarantee
With N lens reviewers the existing `reviewer=<id>` names one of them. The spec has to say how fr knows which dispatches are the lens reviewers and which lens each covers: a multi-valued `reviewer` (a `lens=id` map), or deriving the set from returns. Without that, R10's "a lens has no reviewer's block" has no defined population.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-11-12T17:13:17+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · §3.A says review_return.py is not changed; §3.C changes its id grammar

check: consistency
target: spec
evidence: spec §3.A vs §3.C; packages/fr/src/fr/run/review_return.py:20 (`FINDING_ID_RE`), :56-60, :69-84; run_cmd.py:2568
scope: an internal contradiction in this spec
A `la-r1` id is refused by `parse_review_findings` today, so either the module changes or `fr/lenses/review.py` brings its own parser. Say which. Also define the derived `findings` gate on the exact id grammar, not a bare `l` prefix.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-11-12T17:13:17+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · The record's journal item cannot carry a lens entry as written, and the record kind's version bump is missing

check: codebase
target: spec
evidence: spec §3.B; packages/fr/src/fr/record/model.py:144-171 (`JournalItem` is extra="forbid", no `lens` field, `title` required), model.py:68 (`RECORD_SCHEMA_VERSION = 11`); packages/fr/src/fr/record/apply.py:461-469 (a plan-scope item needs `phase` or `global: true`); packages/fr/src/fr/commands/journal_cmd.py:170-173 and :252-260; .claude/rules/artifact-versioning.md
scope: the spec's own addition path
Adding `lens` to `JournalItem` changes the record's shape (record kind 11 to 12, a migration, a validator). The record example omits the required `title` and does not say how a plan-scope addition from a non-phase step satisfies the phase-or-global rule. The CLI form omits `--scope`, `--slug` and `--title`.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-11-12T17:13:17+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · "The adding step recorded with it" has no field or header token, and no lens id grammar is given

check: consistency
target: spec
evidence: spec §3.B, R5, §3.D table; packages/fr/src/fr/journal/model.py:121-182, :353-371 (`_HEADER_FIELDS`), :404-414, :88 (`_STAMPING_KINDS`)
scope: R5 and R12 depend on this information
Nothing in the design carries the adding step. Name the token and who stamps it; the CLI path has no step. Define the lens id grammar (whitespace-free, safe as a header token and in an entry id). Say `lens` joins `_STAMPING_KINDS` and the validator couples `lens=` to `kind=lens`.

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-11-12T17:13:17+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · R5's journal placement does not match how step records choose a journal

check: consistency
target: spec
evidence: spec R5, §2 Background, §3.B; packages/fr/src/fr/workflow/artifacts.py:132-138 (`journal_scope`); plugins/super-fr/workflows/fr-goal-light.yaml:58-65; plugins/super-fr/workflows/fr-goal.yaml:196-200 (`deliver` emits no journal)
scope: R5 and the Background claim are this spec's
A record entry lands in the scope its step emits, not by whether a plan exists, and `deliver` can add nothing through its record. Reword R5 and correct the Background.

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-11-12T17:13:17+00:00 state=open review_scope=in -->
### s8 · finding [open] (reviewer: in scope) · A run at deliver cannot "finish on the shape it started with"; drift refuses it and reshape refuses too

check: codebase
target: spec
evidence: spec §3.C "Drift (R13)", R13; run_cmd.py:845-870 (`_check_step_drift`); packages/fr/src/fr/run/reshape.py:71-78
scope: the spec's own migration story for in-flight runs
A run whose cursor is on `deliver` fails drift on every command and reshape refuses it. Either design an exemption or say such a run recovers with `fr run adopt <plan-dir> --supersede`, and cover it in a scenario.

<!-- fr:journal kind=finding scope=spec id=s9 created=2026-11-12T17:13:17+00:00 state=open review_scope=in -->
### s9 · finding [open] (reviewer: in scope) · The rule for assigning finding-id letters is unspecified, and the set changes during the step

check: consistency
target: spec
evidence: spec §3.C, decision 12
scope: R10's id checks depend on stable letters
Letters assigned at advance shift when the set grows at resolve, and a late lens has no letter. Define ids that never move, how a late lens is briefed, and the limit.

<!-- fr:journal kind=finding scope=spec id=s10 created=2026-11-12T17:13:17+00:00 state=open review_scope=in -->
### s10 · finding [open] (reviewer: in scope) · The unobserved case leaves the `lenses` evidence and the PR's "files examined" undefined

check: consistency
target: spec
evidence: spec R10, R11, R12, §3.D, §5; run_cmd.py:2541-2543 (`_return_unobserved`)
scope: R11 and R12 promise data this case cannot produce
Where fr cannot read returns it cannot count examined files, and the orchestrator may not pass the count. Say what `lenses` records and what the PR shows then, and what is still enforced.

<!-- fr:journal kind=finding scope=spec id=s11 created=2026-11-12T17:13:17+00:00 state=open review_scope=in -->
### s11 · finding [open] (reviewer: in scope) · `.fr/ci.yaml` is read as base ∪ HEAD, not from HEAD; the spec's analogy is wrong and that pattern closes the loosening risk

check: codebase
target: spec
evidence: spec §3.A, decision 11; packages/fr/src/fr/run/ci_evidence.py:101-110 (`declared_gates`)
scope: the spec's design choice rests on a misread precedent
Taking path rules as base ∪ HEAD would still let one PR add its first rule and use it, while stopping a branch from removing a review. Either adopt the union or fix the analogy and keep the disclosure as a deliberate choice.

<!-- fr:journal kind=finding scope=spec id=s12 created=2026-11-12T17:13:17+00:00 state=open review_scope=in -->
### s12 · finding [open] (reviewer: in scope) · The new derived `lenses` evidence must join fr's verifiable and derived sets, or resolve refuses the step

check: codebase
target: spec
evidence: spec §3.C "Evidence (R11)"; packages/fr/src/fr/workflow/artifacts.py:98 (`DERIVED_EVIDENCE`); run_cmd.py:1611-1621 (`_VERIFIABLE_EVIDENCE`), :1651-1663 (`_DERIVED_FROM`), :1898-1906
scope: needed for the spec's own step to resolve
Name the registration: `lenses` in `DERIVED_EVIDENCE`, `_VERIFIABLE_EVIDENCE` and `_DERIVED_FROM`, and a witness in `_verified_evidence`.

<!-- fr:journal kind=finding scope=spec id=s13 created=2026-11-12T17:13:17+00:00 state=open review_scope=in -->
### s13 · finding [open] (reviewer: in scope) · The prose-only Test Plan becomes one step that owes an outcome before archive

check: consistency
target: spec
evidence: spec `## Test Plan`, decision d6; packages/fr/src/fr/spec.py:633-677; packages/fr/src/fr/archive.py:803-822 and :858-866
scope: may be the accepted cost of a prose Test Plan
fr reads the sentence as Test Plan step 1 and `fr archive` refuses until its outcome is recorded. Say in the spec that the step is closed `--na` at close-out.

<!-- fr:journal kind=finding scope=spec id=s14 created=2026-11-12T17:13:17+00:00 state=open review_scope=in -->
### s14 · finding [open] (reviewer: in scope) · A path rule that requires a disabled lens is neither refused nor defined

check: consistency
target: spec
evidence: spec R3, R6, §3.B
scope: a gap in this spec's config rules
`disable: [security]` with a rule requiring `security` passes R3 and the rule is silently dropped. Have `fr lenses check` refuse it, or say the requirement overrides the disable.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-11-12T17:13:17+00:00 -->
### spec-review · review · independent spec review: 14 findings

Decisions: d1, d4, d6, d8 and d9 are honoured. d7 supersedes d2 and d3 and is honoured (the phase review gets no lens; path rules are kept). d5 is adapted to feature level, consistent with d7. The retired row and three reworded rows match the rewritten design. The Verification section parses.
verified:
- plugins/super-fr/workflows/fr-goal.yaml:101-216 — grouped implement, journal-check (cli), deliver
- plugins/super-fr/workflows/fr-goal-light.yaml:71-115 — same tail, member for member
- packages/fr/src/fr/run/review_return.py:18-84 — `review-findings` fence, several-reviewer letters, `review_findings_rule`
- packages/fr/src/fr/commands/run_cmd.py:2515-2611 — reviewer-return check, `unobserved=reviewer-return`
- packages/fr/src/fr/commands/run_cmd.py:3293-3362 — derived findings witness
- packages/fr/src/fr/commands/run_cmd.py:845-870 — `_check_step_drift`
- packages/fr/src/fr/run/reshape.py:40-99 — reshape inserts an added step pending, only after the cursor
- packages/fr/src/fr/journal/model.py:29-47 — closed `JournalKind` (owed = 2, op = 3)
- packages/fr/src/fr/artifacts/registry.py:415-427 — journal kind current_version=3
- packages/fr/src/fr/artifacts/journal_owed.py, journal_op.py — the stamp-only migration precedent
- packages/fr/src/fr/proportionality.py:10-60,112-127 — merge-base..HEAD diff, EXEMPT_PREFIXES
- packages/fr/src/fr/record/pr_body.py:70-78,999-1033 — REQUIRED_SECTIONS and render order
- packages/fr/src/fr/artifacts/trigger.py:90 — READ_ONLY_COMMANDS
- packages/fr/src/fr/verification/spec_section.py:34-155 — the spec's `## Verification` parses
- packages/fr/src/fr/spec.py:475,536-555 — the spec's `## Test Plan` heading is exact
- plugins/super-fr/verifications/*.yaml, tests/unit/test_tripwire_shipped_verifications.py — the arrangement the lenses copy
- plugins/super-fr/skills/fr-goal/SKILL.md:102,108,111 — §6, §7, §8
- docs/explainers/01-fr-goal.md; .fr/docs.yaml:1-6

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-11-12T17:13:17+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: `fr run advance` never completes a `kind: agent` step; §3.C assumes it does on an empty lens set

advance is unchanged; on an empty set the brief says so and the orchestrator resolves the step with no review or reviewer (R11, §3.C Advance, decision 14); the return-checked scenario covers it.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-11-12T17:13:17+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: The review/reviewer/findings verifiers refuse a flat step that emits journal:plan; "held as on a phase review" needs a new evidence target

§3.C designs a third, feature-level evidence target over the plan journal and routes review, reviewer, findings and the returned-findings check through it.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-11-12T17:13:17+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: `reviewer` evidence holds one dispatch id; the lens review has one reviewer per lens

On this step `reviewer` is a `<lens>=<dispatch-id>` map, one per lens in the set; R10 and §3.C say what fr refuses with and without readable returns.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-11-12T17:13:17+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: §3.A says review_return.py is not changed; §3.C changes its id grammar

§3.A now says `parse_review_findings` takes the id grammar as a parameter; §3.C gives the exact lens grammar and defines the findings gate on it.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-11-12T17:13:17+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: The record's journal item cannot carry a lens entry as written, and the record kind's version bump is missing

§3.B names both shape changes (journal 3 to 4, record 11 to 12, each with migration and validator), gives the record item with its required title, the global rule for non-phase steps, and the full CLI form.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-11-12T17:13:17+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: "The adding step recorded with it" has no field or header token, and no lens id grammar is given

§3.B adds the `step=` token stamped by fr from the record's step, says the CLI path records none, gives the lens id grammar (also in R3 and §3.A), and adds `lens` to `_STAMPING_KINDS` with the validator coupling.

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-11-12T17:13:17+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: R5's journal placement does not match how step records choose a journal

R5 now says an addition lands in the journal its step writes; the Background states the scope rule, the light shape's case and that `deliver` emits no journal.

<!-- fr:journal kind=finding scope=spec id=s8-resolved created=2026-11-12T17:13:17+00:00 state=fixed resolves=s8 -->
### s8-resolved · finding [fixed] · resolves s8: A run at deliver cannot "finish on the shape it started with"; drift refuses it and reshape refuses too

R13 and §3.C Drift say a run at `deliver` is carried over by `fr run adopt --supersede`; the accumulate scenario covers both cases.

<!-- fr:journal kind=finding scope=spec id=s9-resolved created=2026-11-12T17:13:17+00:00 state=fixed resolves=s9 -->
### s9-resolved · finding [fixed] · resolves s9: The rule for assigning finding-id letters is unspecified, and the set changes during the step

Finding ids are `l-<lens>-r<k>`, carrying the lens id, so nothing moves when the set grows and there is no limit; a refusal over a late lens prints its brief (R10, §3.C, decision 15).

<!-- fr:journal kind=finding scope=spec id=s10-resolved created=2026-11-12T17:13:17+00:00 state=fixed resolves=s10 -->
### s10-resolved · finding [fixed] · resolves s10: The unobserved case leaves the `lenses` evidence and the PR's "files examined" undefined

R11, §3.C Evidence, §3.D and §5 define the unobserved value, the PR's wording and what is still enforced.

<!-- fr:journal kind=finding scope=spec id=s11-resolved created=2026-11-12T17:13:17+00:00 state=fixed resolves=s11 -->
### s11-resolved · finding [fixed] · resolves s11: `.fr/ci.yaml` is read as base ∪ HEAD, not from HEAD; the spec's analogy is wrong and that pattern closes the loosening risk

Path rules are the default branch's together with the branch's (R6, §3.A, decision 11), the `.fr/ci.yaml` rule; lens text stays read from the branch with the change stated on the PR.

<!-- fr:journal kind=finding scope=spec id=s12-resolved created=2026-11-12T17:13:17+00:00 state=fixed resolves=s12 -->
### s12-resolved · finding [fixed] · resolves s12: The new derived `lenses` evidence must join fr's verifiable and derived sets, or resolve refuses the step

§3.C Evidence names the registration in `DERIVED_EVIDENCE`, `_VERIFIABLE_EVIDENCE`, `_DERIVED_FROM` and `_verified_evidence`.

<!-- fr:journal kind=finding scope=spec id=s13-resolved created=2026-11-12T17:13:17+00:00 state=fixed resolves=s13 -->
### s13-resolved · finding [fixed] · resolves s13: The prose-only Test Plan becomes one step that owes an outcome before archive

The Test Plan is now one numbered step that says it is recorded not applicable at close-out, with the command.

<!-- fr:journal kind=finding scope=spec id=s14-resolved created=2026-11-12T17:13:17+00:00 state=fixed resolves=s14 -->
### s14-resolved · finding [fixed] · resolves s14: A path rule that requires a disabled lens is neither refused nor defined

R3 and §3.A: `fr lenses check` refuses a config that disables a lens a rule in force requires.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-12T17:13:20+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  review-lenses-accumulate: none
  review-lenses-effective-set: none
  review-lenses-path-rules: none
  review-lenses-reviewer-return-checked: none
  review-lenses-shown-on-pr: none
row_kinds:
  review-lenses-accumulate: candidate
  review-lenses-effective-set: candidate
  review-lenses-path-rules: candidate
  review-lenses-reviewer-return-checked: candidate
  review-lenses-shown-on-pr: candidate
run_gate: none
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-12-review-lenses-p2 created=2026-11-12T17:16:46+00:00 -->
### phase-split-2026-11-12-review-lenses-p2 · decision · ask: adding lenses and path rules (R4-R7) is its own ask, with two artifact migrations reviewed apart from the lens set

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-12-review-lenses-p3 created=2026-11-12T17:16:56+00:00 -->
### phase-split-2026-11-12-review-lenses-p3 · decision · ask: the lens-review step and its evidence gate (R8-R11, R13) is its own ask and changes the gate every review step uses

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-12-review-lenses-p4 created=2026-11-12T17:17:05+00:00 -->
### phase-split-2026-11-12-review-lenses-p4 · decision · ask: the PR section, skills, agents and docs (R12, R14) is its own ask

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-12-review-lenses-p2 created=2026-11-12T17:17:16+00:00 -->
### tier-2026-11-12-review-lenses-p2 · decision · hard: two artifact shape changes with migrations (journal 4, record 12) that every reader relies on

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-12-review-lenses-p3 created=2026-11-12T17:17:25+00:00 -->
### tier-2026-11-12-review-lenses-p3 · decision · hard: changes the evidence gate in run_cmd.py that every review step resolves through

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-1 created=2026-11-13T04:37:01+00:00 -->
### test-plan-step-1 · discovery · Test Plan step 1: n/a

Step: [developer] No post-merge step exists: every row is proven on a candidate build before merge. At close-out, record this step as not applicable (`fr closeout outcome --step 1 --na`).

Reason: No post-merge step exists: every row is proven on a candidate build before merge.
