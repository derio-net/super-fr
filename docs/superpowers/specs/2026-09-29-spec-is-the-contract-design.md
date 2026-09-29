# The spec is the contract: remove the input layer from fr-goal — design

**Date:** 2026-09-29 · **Branch:** `feat/spec-is-the-contract` · **Release:** 5.0.0 (major)
**Origin:** operator decision in a brainstorm on 2026-09-29, after take 10's live walk (#817).
Built by hand in an fr-isolation workspace, not by an fr-goal run: an fr-goal run would push this spec through the gates it removes.

## Requirements

R1. The operator's input (an optional issue, an optional initial message, and the answers to the brainstorm's questions) is an input to the brainstorm step only. No step after brainstorm reads it, receives it in a brief, or is gated on it.
R2. The spec and the plan are the output of the questioning. After brainstorm, the spec is the contract: a requirement the spec doesn't state is not implemented, and a spec defect is fixed by fixing the spec.
R3. The brief is still stored verbatim as a journal entry at brainstorm, for the record.
R4. The question-round mechanics stay as they are: labels, one dialog at a time, rounds counted against the transcript (#767, #784).
R5. The spec's `## Requirements` section is a plain numbered list, one requirement per line (`R1. <text>`), with no quote, no source column, no "Deferred from input" section, and no gate on its content.
R6. Spec review checks the spec against the codebase and the operator's recorded decisions, and the spec against itself, as it did in 4.28.0. The light path's combined spec-and-plan review keeps its plan section.
R7. Every change since 4.28.0 that is not part of the input layer keeps working: phase sizing and tier criteria, the light path, UI evidence, the always-on close-out, services, `verify: post-merge` rows, and the PR body's Post-merge and Tests sections.
R8. Existing artifacts keep loading: a record at version 6 migrates to 7, journals parse without migration, and a spec with the old three-column Requirements table still parses.
R9. `AGENTS.md` states the principle in one sentence, so a future session sees the rule before proposing to break it.
R10. The release is 5.0.0: a CLI verb and journal flags are removed.

## Design

### Background

4.29.0 (#762) added requirements traceability after a spec paraphrased the operator's brief and invented a card click (#759). Six PRs extended it: #786, #788, #791, #819, #827 and #833 (about +14,300 lines, about 2,400 of them in `packages/*/src`). It added four derived gates, `requirements`, `coverage`, `fidelity` and `requirement-rows`. It sent the raw input into implement and review briefs, and it grew the fr-goal skill from 4,271 to 6,149 words and the spec reviewer from 756 to 2,063.

Each mechanical check produced its own failures, and each failure produced another check. Take 10 (#817) spent 31 minutes, 38% of one delivery, in a 13-dispatch spec-review loop over the coverage partition (#808). About 15 of the 53 issues filed since 09-28 are about the layer itself, and #846 and #847 propose extending it again. This design removes it and restores the 4.28.0 pipeline shape, keeping every unrelated change made since.

### A. Removed outright (R1, R2)

- `fr/fidelity.py` and `fr/operator_input.py`.
- The derived evidence names `requirements`, `coverage`, `fidelity` and `requirement-rows`: from `_VERIFIABLE_EVIDENCE`, `_DERIVED_EVIDENCE` and `_DERIVED_FROM` in `run_cmd.py`, and from both shipped workflows (`fr-goal.yaml` and `fr-goal-light.yaml`, package and plugin copies). Their witnesses go too: the traceability block in `run_cmd.py` (`_REQUIREMENTS_EVIDENCE`, `_RequirementsCapture`, `_predates_requirements`, `_requirements_capture`, the four `_*_witness` functions) and the predates logic in `_unevidenced_units`. The generic refusal printer `_requirements_refusal`, which `_visual_witness` also uses, stays under a neutral name.
- The workflows' evidence lists return to 4.28.0's: brainstorm none; spec-review `[review, reviewer, findings]`; deliver `[tests, proportionality, visual]`. The light path's `spec-plan-review` and `deliver` follow the same way. Only evidence lists change, so `_check_step_drift` (which compares step ids) accepts existing cursors.
- `fr spec requirements` (`spec_cmd.py`); `fr spec status` stays.
- `operator_input` in dispatch briefs: `_build_member_brief`, `_print_member_dispatch`, `_load_operator_input` and `_advance_group` in `run_cmd.py`; and the "Operator input" section of `fr journal handoff` (`journal_cmd.py`, `compose_handoff`).
- The `fr-phase-reviewer` agent, which exists only because of #833. Review-phase goes back to 4.28.0's generic reviewer brief. The deletion reaches the `agent:` line in `fr-goal.yaml`, its branch in `hooks/fr-phase-executor-guard.sh`, the allowlist in `scripts/install.sh` and `scripts/ensure-phase-executor-allowlist.sh`, its mention in `plugins/super-fr/rules/fr-isolation-required.md` and `.claude/rules/fr-isolation-required.md`, and its row in `fr/harness/parity.yaml`.
- The `delegated` answer marker ("your call"), the `unconfirmed` resolution state (a spec-review finding is fixed or recorded as out of scope, as before), and `journal add --delegated`.
- The PR body sections "Input coverage", "Design inventory" and "Built without operator confirmation", and the unconfirmed bucket in Findings (`record/pr_body.py`).
- The record template hints for `delegated` and invented or reinterpreted findings (`record/template.py`). The `verify: post-merge` hint stays.

### B. `requirements.py` becomes a plain-list parser (R5, R7, R8)

The module keeps its name, to limit churn in its importers. It keeps only what the rest of fr uses: the R-id grammar (`R[1-9][0-9]*`), `origin_fragment`, `rows_citing`, `is_cited`, `spec_emitter`, `run_spec` and `load_spec_matrix`. `parse_requirements` now reads lines of the form `R<n>. <text>` under `## Requirements`. For specs written before this change, it also reads the three-column table and takes the `id` and `requirement` columns, ignoring `source`. `has_requirements_table` becomes `has_requirements` and is true for either form.

Removed: `Source`, `SourceKind`, `Deferred`, `CoverageCounts`, `is_input_entry`, the quote grammar (`_INPUT_SOURCE_RE`, `SOURCE_FORMS`, `_extract_quote`, `_parse_sources`), `quote_matches`, `normalise`, `check_requirements`, `check_coverage` and the coverage block, `_REDISPATCH` and `REQUIREMENTS_PREDATES`.

Phase sizing (`phase_sizing.py`, `plan_ops._phase_sizing_issues`, `proportionality._phases`) and visual evidence (`run/visual.py`, `_visual_witness`) switch to the new parser. Their messages say "Requirements list", not "table". An R-id the plan doesn't cover still only warns.

### C. Artifacts (R8)

- **Record kind 6 → 7.** `JournalItem.input` stays: it marks the stored-brief entry. `JournalItem.delegated` and the `unconfirmed` member of `ResolutionState` are removed. Per the artifact-versioning rule, today's model is frozen as `RecordV6` in `fr/record/legacy.py` (the same pattern as `fr.run.legacy.RunStateV4`), with its vocabularies inlined and its source hash pinned, and every record migration hop reads through it. The new migration (`fr/artifacts/record_contract.py`, imported by `fr/artifacts/__init__.py`) drops `delegated`. It leaves a record whose resolution is `unconfirmed` byte-identical and reports it as that artifact's failure: that state has no honest equivalent. No `*.records` files exist today, so nothing actually migrates. `record/apply.py` loses `unconfirmed_refusal` and the `delegated` pass-through.
- **Journals** are unstamped and parse tokens by name, so an unknown token is ignored. The parser stops recognising `delegated=` and the `unconfirmed` state; `input=true` stays. Only files under `implemented/` carry the removed tokens, and those are frozen and never parsed. No migration.
- **The acceptance matrix** stays at version 3; `Row.verify` is not input-layer.
- **Run cursors** keep loading: only step ids are drift-checked.

### D. Prose (R1, R2, R4, R6)

Every input-layer passage returns to its 4.28.0 wording. Everything else added since stays.

- **`fr-goal/SKILL.md`.**
  - §1 opens again with "Invoke `fr-brainstorming`. Explore, collect every operator-owned decision…". It keeps the #767/#784 label and one-dialog text, and drops "questions whose answers are interpretations of the input come first".
  - §2 is 4.28.0's "the spec against the Q&A decisions and codebase reality; fix every finding in scope". Traceability-first, the three blocks, the dropped/invented/reinterpreted rules, "never re-cut a span" and the re-dispatch text all go.
  - §6 returns to the generic reviewer brief.
  - The light-path section loses its coverage and fidelity mentions.
- **`fr-brainstorming/SKILL.md`.**
  - §1 is "Brainstorm", with one short paragraph: record the brief verbatim, for the record.
  - §2 describes the plain `## Requirements` list.
  - §3 keeps acceptance rows citing `#R<n>` and `verify: post-merge`.
  - The "your call" rule goes.
- **`fr-acceptance/SKILL.md`** says "Requirements list" and loses the `requirement-rows` mention.
- **`fr-plan`** is unchanged: phase sizing stays.
- **`fr-spec-reviewer.md`** returns to 4.28.0's "three things, in this order": decisions, codebase, itself. It keeps the light path's "When the brief names a plan too" section.
- **`fr-phase-executor.md`** loses "fetch the operator input yourself" and the operator-input bullet, and keeps its light-path additions.
- **`AGENTS.md`** loses the lines #762 added and gains the principle (R9): "The spec is the contract: nothing after brainstorm reads the raw input, and a requirement the spec does not state is a spec defect, fixed in the spec."
- **Generated mirrors** (`.opencode/agent`, `.opencode/skills`, `.opencode/instructions`, `.hermes/skills`, `.hermes/SOUL.d`) are regenerated with `scripts/sync-opencode.py` and `scripts/sync-hermes.py`.
- **`docs/explainers/01-fr-goal.md`** loses the traceability, relay, fidelity and phase-reviewer passages. Its `.html` is regenerated with the blog-craft renderer, after the byte-for-byte check on the unmodified page.

### E. Acceptance matrix

- **Deleted.** About 18 input-layer rows are removed by hand, because no verb deletes a row: the `requirements-*` rows except `requirements-post-merge-rows`, the three `raw-input-relay-*` rows, and the six `spec-fidelity-*` rows, including the failing `spec-fidelity-live-invention-caught`. The PR body lists each id removed. This is not a status move: the features those rows describe no longer exist.
- **Reworded** where they name the table, a removed gate or the phase reviewer: `requirements-post-merge-rows`, the `phase-sizing-*` rows, the `light-path-*` rows and `fr-goal-independent-spec-review`.
- **Added** for this spec: see the Test Plan.
- The three reports are regenerated with `fr acceptance report --deterministic`.

### F. Delivery

- One PR from `feat/spec-is-the-contract`, with a change fragment `.changes/feat-spec-is-the-contract.yaml` saying `bump: major`, so the release is 5.0.0 (R10). No version surface is edited by hand.
- #828 (`deliver-handoff`) merges first, and this branch rebases onto it.
- Before the PR is marked ready, an independent review by a subagent that did not write the code checks two things: that nothing outside the input layer was lost (phase sizing, light path, UI evidence, close-out, tiers), and that no path after brainstorm still reads the input.

### G. Out of scope

- Closing the issues this makes moot (#808, #810, #829, #830, #846, #847, #764, and the reopen suggestions from #817). That happens with the operator afterwards.
- Re-scoping #823 to its parts that don't touch the input (session identity, cost, question answers, screenshot reads), salvaged from PR #837.
- Distilling more of the input into Requirements at brainstorm: a possible later direction that stays inside the brainstorm boundary.
- A test guarding against regrowth. The operator chose the `AGENTS.md` principle plus review instead.

## Test Plan

Automated (CI, `uv run pytest`):

1. **No input gates (R1).** Both shipped workflows pass `fr workflow check`, and their evidence lists are the ones in §A (the shipped-workflow tripwire pins them). The implement-phase and review-phase dispatch briefs carry no `operator_input` key. `fr journal handoff` prints no "Operator input" section.
2. **Plain Requirements (R5, R8).** `parse_requirements` reads an `R<n>. <text>` list and an old three-column table to the same ids and text. Phase sizing's "serves N of N requirements" and visual evidence's `rows_citing` work on both forms. A spec without the section is skipped as before.
3. **Brief and questions stay (R3, R4).** The brainstorm record stores the brief as an `input=true` journal entry. The question-round tests (`test_run_question_rounds.py` and the round-label tests) pass unchanged.
4. **Record 7 (R8).** The record chain reaches 7 from 1, hop by hop. A version 6 record carrying `delegated` migrates with the field dropped. A version 6 record whose resolution is `unconfirmed` is left byte-identical and reported. The frozen `RecordV6` source hash is pinned.
5. **Nothing else lost (R7).** The phase-sizing, light-path, UI-evidence, close-out, services and tier tests pass, with their fixtures moved to the plain list where they used the table.
6. **Prose and mirrors.** Both mirror tripwires and the agent-mirror test pass. The skill-token, neutrality and parity tripwires pass without `fr-phase-reviewer`.

Post-merge, operator-driven:

7. **Dry run on 5.0.0 (R1, R2, R6).** Run super-fr-3's feature-C brief once on 5.0.0 before the talk recording. It passes if brainstorm records the brief and the answers, the spec carries a plain `R1…Rn` list, spec review runs once with no coverage or partition loop, and deliver resolves. The recording agent's #820 benchmark may run on the same build.

Acceptance rows added (`origin` this spec's R-ids):
- `spec-contract-no-input-gates` (items 1, 3), `ci`;
- `spec-contract-plain-requirements` (item 2), `ci`;
- `spec-contract-record-v7` (item 4), `ci`;
- `spec-contract-dry-run` (item 7), `not-implemented`, `verify: post-merge`.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-29-spec-is-the-contract | `derio-net/super-fr` | `2026-09-29-spec-is-the-contract` | — |
