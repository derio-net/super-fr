# Journal: 2026-09-28-raw-input-relay

<!-- fr:journal kind=discovery scope=spec id=input-batch-brief created=2026-09-28T19:33:51+00:00 input=true -->
### input-batch-brief · discovery · Operator's batch dispatch brief (raw-input-relay-2), verbatim

/fr-goal implement-phase and review-phase briefs carry the verbatim input; the spec governs, a disagreement is a finding

Batch `raw-input-relay-2` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#778: implement-phase and review-phase dispatches don't carry the raw input: executor and reviewer see the brief only through the spec (#759 follow-up)
implement-phase and review-phase briefs carry the spec and plan only; the verbatim input (already in the spec journal's kind=discovery entry) never reaches executor or reviewer: 0 hits for brief phrases in their take-9 sessions.
Note: Operator-prioritised. Batch `raw-input-relay` (wave 6): attach the input entry + recorded answers read-only; the spec governs, a disagreement is a finding. Independent of #773.

## Why these belong together
Retry of the batch cancelled on 2026-09-28 at its question gate (#783): dispatch only after question-order (#783) merges. Wave 6, moved up from spec-fidelity: it changes only the dispatch briefs and does not depend on #773's review rework, and it is the cheapest fix for the relay loss take 9 showed (0 brief phrases in the executor's and reviewer's sessions). Attach the spec journal's kind=discovery input entry and the operator's recorded answers read-only. Rebase against requirements-gate and ui-evidence if all touch fr-goal SKILL.md.

## Delivery rules
- Work on branch `feat/batch-raw-input-relay-2`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#778
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=discovery scope=spec id=input-issue-778 created=2026-09-28T19:33:51+00:00 input=true -->
### input-issue-778 · discovery · super-fr#778 title and body, verbatim

implement-phase and review-phase dispatches don't carry the raw input: executor and reviewer see the brief only through the spec (#759 follow-up)

## What happened

Follow-up to #759, whose reframing made the spec the requirements carrier. In take 9 of the super-fr-3 feature-C recording (fr 4.29.2), the phase executor and the code reviewer again saw the brief only through the spec's requirement text and quotes: 0 hits in their sessions (`ses_f17668775f…`, `ses_f175c5041f…`) for brief phrases such as "Business rules", "680–720" or "same style". Every clause the spec dropped (#773) was invisible to the two agents that build and check the feature.

The raw input is already stored verbatim in the spec journal (the `kind=discovery` entry carrying `input`).

## Expected

The dispatch briefs for `implement-phase` and `review-phase` attach that verbatim input entry (plus the operator's recorded answers) as a read-only reference next to the spec and plan, with one rule: the spec governs; when the raw input says something the spec doesn't, report it as a finding rather than silently implement or ignore it.

Cheap (one journal entry per dispatch) and it gives the last two hops a way to catch what the relay lost, which matters more as the executor model gets smaller.

<!-- fr:journal kind=decision scope=spec id=d1-brief-and-handoff created=2026-09-28T19:33:51+00:00 -->
### d1-brief-and-handoff · decision · Carrier: a brief key AND a handoff section

Q (Round 1 · question 1 of 5): How should the verbatim input reach the executor and the reviewer?
A (operator): Brief key + handoff. fr adds an `operator_input` key to every implement-phase/review-phase member brief (input entries + recorded answers + the "spec governs" rule, verbatim), relayed verbatim like long_commands; `fr journal handoff --phase N` also gets a read-only "Operator input" section, so an executor that runs the handoff itself gets it even if the relay drops it.

<!-- fr:journal kind=decision scope=spec id=d2-all-spec-decisions created=2026-09-28T19:33:51+00:00 -->
### d2-all-spec-decisions · decision · Recorded answers = every decision entry of the spec journal

Q (Round 1 · question 2 of 5): What counts as "the operator's recorded answers"?
A (operator): All spec decisions — every kind=decision entry in the run's spec journal.

<!-- fr:journal kind=decision scope=spec id=d3-ordinary-gated-finding created=2026-09-28T19:33:51+00:00 -->
### d3-ordinary-gated-finding · decision · A lost-clause disagreement is an ordinary gated plan-journal finding

Round 1 · question 3 of 5 was answered with a question: "But we already have a mechanism that decides between input and operator answers, in the journal and the result becomes the spec. How does that happen? Is the mechanism lossy?" Answered: brainstorm's Requirements rows quote the input or cite a decision (an answer overriding the input is cited as that decision); `requirements` checks the quotes/decisions/rows mechanically; spec-review's coverage gate checks the input is partitioned into spans. It IS lossy in two places: fidelity of a requirement's text to its span is unchecked (check_coverage's docstring; #773), and executor/reviewer act on the requirement text, never the input (#778).
Q (Round 2 · question 1 of 3, re-asking round-1 Q3): When the input says something neither the spec nor a recorded decision covers, how is it recorded?
A (operator): Ordinary gated finding — a plan-journal finding against that phase, id prefix `input-`, review_scope in, gating the phase review; resolved fixed (spec amended then built), refuted (a decision covers it) or deferred with a tracking issue. A deliberate override by a decision is NOT a finding. No schema change.

<!-- fr:journal kind=decision scope=spec id=d4-no-relay-check created=2026-09-28T19:33:51+00:00 -->
### d4-no-relay-check · decision · No verification that the relay reached the agent, in this change

Q (Round 2 · question 2 of 3): Should fr verify the relay happened?
A (operator): No check in this change — brief key + handoff carry it, prose says relay verbatim.

<!-- fr:journal kind=decision scope=spec id=d5-unit-tests-suffice created=2026-09-28T19:33:51+00:00 -->
### d5-unit-tests-suffice · decision · No post-merge live-run acceptance row; unit tests suffice

Q (Round 2 · question 3 of 3): Should a live fr-goal run confirm input phrases reach the executor's and reviewer's sessions?
A (operator): "you mean we add an acceptance row to search the sessions for text appearances of the input?!? No, that's too much, unit test suffice"

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-09-28T19:33:52+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: operator-request. Round 1's Q3 was answered with a question ("we already have a mechanism that decides between input and operator answers ... Is the mechanism lossy?"). Answering it needed a code read (fr/requirements.py), so the re-asked Q3 and the two not-yet-asked questions formed a second round.

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-09-28T19:40:02+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · operator_input is widened to every member of the group, not just implement-phase and review-phase

check: traceability
evidence: spec §B "It rides every member brief of the group … a repo-override shape with other members gets it too"; input-issue-778 "The dispatch briefs for `implement-phase` and `review-phase` attach that verbatim input entry"; decision d1-brief-and-handoff "every implement-phase/review-phase member brief"
scope: this change adds the behaviour. It is invented, so it has to be tagged in scope.
resolution: invented
Both the input and d1 limit the relay to the two named members. §B also gives the key to any member of a repo-override grouped shape. That is agent-visible behaviour, and no requirement or decision covers it (R1 says "Every `implement-phase` and `review-phase` dispatch brief"). There are two fixes. Resolve it `unconfirmed` with a note that says other members of an override shape get the key too. Or gate the key on those two member ids, so the literal reading of the input is enough. Do not rewrite R1 to match the design.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-09-28T19:40:02+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · The fail-closed spec-journal load runs after the write-claim, so a parse error leaves a running unit that never got a brief

check: consistency
evidence: spec §A `load` "a journal that fails to parse raises (fail-closed)"; spec §B "the caller (`_advance_group`, via `_print_member_dispatch`) loads it"; packages/fr/src/fr/commands/run_cmd.py:3253 (`items[pending] = "running"`), :3282 (`_save_run_state`), :3134-3135 (`_note_subject` + `_commit_run_writes_now` inside `_print_member_dispatch`, before the brief is printed); Test Plan 1 covers only the `null` case
scope: this change adds the new raise on the dispatch path.
By the time `_print_member_dispatch` runs, the unit is already saved and committed as `running` with an open dispatch attempt. A raise from `operator_input.load` at that point prints no brief. The next `advance` then refuses with ALREADY RUNNING, and only `--redispatch` or `claim --abandoned` gets out. The spec also does not say what `advance` prints or returns on this failure (a traceback or exit 2 with a message). The handoff has an explicit exit 2 (§C, Test Plan 2), but the brief path has nothing equivalent. Fix: load in `_advance_group` before the write-claim at run_cmd.py:3253, and turn a `JournalParseError` into exit 2 with a message naming the spec journal. Add a Test Plan case: an unparseable spec journal refuses the dispatch and leaves the unit un-claimed.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-09-28T19:40:02+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · The handoff skips the operator input when the plan journal has not been written yet, which undercuts R4

check: consistency
evidence: packages/fr/src/fr/commands/journal_cmd.py:748-750 (`if not path.exists(): return` runs before the plan is parsed, so before `spec_path` is known); tests/unit/test_journal_cmd.py:1307 `test_handoff_missing_journal_fails_open`; spec §C lists the no-section cases as only "No spec, a cross-repo spec, or no input entry"; R4 "so an executor that composes its own handoff reads them even when the orchestrator's relay drops them"
scope: R4 is this change's own guarantee, and the path that breaks it is in the command §C modifies.
When no plan journal exists, `fr journal handoff` returns empty output before it parses the plan. It never reaches `spec_path`, so the Operator input section is silently missing on exactly the path R4 is meant to cover. Either compose the operator-input section (and the plan parse) even when the plan journal is absent, or list this as a stated no-section case in §C. Test Plan 2 should cover it either way.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-09-28T19:40:02+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · Input bodies rendered verbatim bring their own `##` headings into the handoff and break its section structure

check: consistency
evidence: spec §A `to_markdown` (section `## Operator input …`, entries under `### <id>`, bodies verbatim); compose_handoff's top-level sections are `## Open findings` / `## Relevant context` / `## Earlier history` / `## Full journal` (packages/fr/src/fr/journal/model.py:778-787); this run's own input bodies contain `## super-fr#778: …`, `## Why these belong together`, `## Delivery rules`, `## What happened`, `## Expected`
scope: this change adds the new section and chooses how it renders.
Issue and batch-brief inputs usually carry level-2 headings. Pasted verbatim under a `###` entry heading, they show up as peers of `## Operator input` and `## Open findings`. An executor reading the handoff cannot tell where the read-only reference ends. For example, "## Delivery rules" reads as a handoff section. Keep the bodies verbatim but put them inside a container: a fenced block with a fence longer than any fence in the body, or a blockquote. Add a test whose input body contains a `##` heading.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-09-28T19:40:02+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · The published fr-goal explainer lists what the executor is given and needs an update, but the spec does not plan one

check: codebase
evidence: docs/explainers/01-fr-goal.md:726-728 ("given the phase's scope, the specification, and the running journal of what earlier phases discovered"); .claude/rules/explainers-currency.md (a shipped skill's pipeline change triggers an explainer update in the same PR, or the PR body records why not)
scope: this change alters what the executor and reviewer are handed. I am unsure the explainer rule counts as a spec concern, so I have tagged it in scope.
After this change the executor and reviewer also get the operator's raw input and recorded answers, plus the rule that the spec governs. The explainer's §6 paragraph would then understate this, and its §2 text about the input entry being "the anchor" should say it now also reaches the build and review hops. §D should add: update 01-fr-goal.md §6 and regenerate the .html per the rule, or state in the PR body that the regeneration is owed.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-28T19:40:02+00:00 -->
### spec-review · review · independent spec review: 5 findings

Decisions: d1 (brief key plus handoff section), d2 (every kind=decision entry; this includes the fr-written gate-question-rounds-brainstorm entry, as d2 reads literally), d3 (an `input-` plan-journal finding, in scope and gating, with no schema change), d4 (non-goal) and d5 (non-goal, no live row) are all honoured. The spec reverses the dispatch half of the archived d0-spec-is-the-carrier (implemented/specs/2026-09-28-requirements-traceability-design.md:41, :63, :121-123, :414-415), which is what the operator's input asks for. The archived spec itself stays frozen. No test asserts that the input never reaches a handoff or brief. The only claim is the matrix row's acceptance text (matrix.yaml:4298-4299), and its levels test the input token round-trip, not absence. So §E is accurate. Matrix rows for R1-R6 already exist (matrix.yaml:4424-4456).

input-coverage:
```input-coverage
| span | coverage |
|---|---|
| "/fr-goal implement-phase and review-phase briefs carry the verbatim input; the spec governs, a disagreement is a finding" | R1, R3 |
| "Batch `raw-input-relay-2` of derio-net/super-fr: 1 issues, delivered as ONE pull request." | context |
| "## super-fr#778: implement-phase and review-phase dispatches don't carry the raw input: executor and reviewer see the brief only through the spec (#759 follow-up)" | context |
| "implement-phase and review-phase briefs carry the spec and plan only; the verbatim input (already in the spec journal's kind=discovery entry) never reaches executor or reviewer: 0 hits for brief phrases in their take-9 sessions." | context |
| "Note: Operator-prioritised. Batch `raw-input-relay` (wave 6):" | context |
| "attach the input entry + recorded answers read-only;" | R1, R2 |
| "the spec governs, a disagreement is a finding." | R3 |
| "Independent of #773." | context |
| "## Why these belong together" | context |
| "Retry of the batch cancelled on 2026-09-28 at its question gate (#783): dispatch only after question-order (#783) merges. Wave 6, moved up from spec-fidelity: it changes only the dispatch briefs and does not depend on #773's review rework, and it is the cheapest fix for the relay loss take 9 showed (0 brief phrases in the executor's and reviewer's sessions)." | context |
| "Attach the spec journal's kind=discovery input entry and the operator's recorded answers read-only." | R1, R2 |
| "Rebase against requirements-gate and ui-evidence if all touch fr-goal SKILL.md." | context |
| "## Delivery rules" | context |
| "- Work on branch `feat/batch-raw-input-relay-2`." | context |
| "- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:" | context |
| "Closes derio-net/super-fr#778" | context |
| "- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels." | context |
| "implement-phase and review-phase dispatches don't carry the raw input: executor and reviewer see the brief only through the spec (#759 follow-up)" | R5 |
| "## What happened" | context |
| "Follow-up to #759, whose reframing made the spec the requirements carrier. In take 9 of the super-fr-3 feature-C recording (fr 4.29.2), the phase executor and the code reviewer again saw the brief only through the spec's requirement text and quotes: 0 hits in their sessions (`ses_f17668775f…`, `ses_f175c5041f…`) for brief phrases such as "Business rules", "680–720" or "same style". Every clause the spec dropped (#773) was invisible to the two agents that build and check the feature." | context |
| "The raw input is already stored verbatim in the spec journal (the `kind=discovery` entry carrying `input`)." | context |
| "## Expected" | context |
| "The dispatch briefs for `implement-phase` and `review-phase` attach that verbatim input entry" | R1 |
| "(plus the operator's recorded answers)" | R2 |
| "as a read-only reference next to the spec and plan," | R1 |
| "with one rule:" | R3 |
| "the spec governs; when the raw input says something the spec doesn't, report it as a finding rather than silently implement or ignore it." | R3 |
| "Cheap (one journal entry per dispatch) and it gives the last two hops a way to catch what the relay lost, which matters more as the executor model gets smaller." | context |
```
verified:
- packages/fr/src/fr/commands/run_cmd.py:2854 — `_build_member_brief`, pure; `long_commands` key at :2891
- packages/fr/src/fr/commands/run_cmd.py:3106 — `_print_member_dispatch`, the one caller of `_build_member_brief` (:3143)
- packages/fr/src/fr/commands/run_cmd.py:3152 — `_advance_group`; write-claim :3253, save :3282, print :3284
- packages/fr/src/fr/commands/run_cmd.py:2490 — `_build_brief` (flat/group brief)
- packages/fr/src/fr/requirements.py:538 — `run_spec(state)`; :87 `is_input_entry`; :446 `check_coverage`
- packages/fr/src/fr/journal/model.py:75 `spec_journal_slug`; :231 `resolve_journal_read_path`; :668 `compose_handoff`
- packages/fr/src/fr/commands/journal_cmd.py:715 — `fr journal handoff`; early return when the journal is missing :749-750
- packages/fr/src/fr/parser.py:138 — `parse(plan_dir)`; `Plan.spec_path` :56, resolved :216-220
- packages/fr/src/fr/harness/long_commands.py:53 — `long_command_rule(harness)`
- plugins/super-fr/workflows/fr-goal.yaml:122,128 — grouped `implement` members are exactly `implement-phase` and `review-phase`
- plugins/super-fr/skills/fr-goal/SKILL.md §5/§6; plugins/super-fr/agents/fr-phase-executor.md:49 "## Inputs"
- docs/acceptance/matrix.yaml:4296-4309 — `requirements-input-in-spec-journal`
- no test asserts that input stays out of a handoff or brief

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-09-28T19:40:02+00:00 state=open resolves=sr-1 unconfirmed=true -->
### sr-1-resolved · finding [unconfirmed] · resolves sr-1: operator_input is widened to every member of the group, not just implement-phase and review-phase

Built as designed: `operator_input` rides every member brief of a grouped `for_each: phase` step. In the shipped fr-goal shape those members are exactly implement-phase and review-phase; a repo-override shape with other grouped members gets the key too. Gating on member ids was rejected because it drifts with the manifest.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-09-28T19:40:02+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: The fail-closed spec-journal load runs after the write-claim, so a parse error leaves a running unit that never got a brief

Spec §B now loads before the write-claim and refuses with exit 2 leaving the unit unclaimed; Test Plan 1 covers it.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-09-28T19:40:02+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: The handoff skips the operator input when the plan journal has not been written yet, which undercuts R4

Spec §C parses the plan first; with no plan journal the handoff is the operator-input section alone; Test Plan 2 covers it.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-09-28T19:40:02+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: Input bodies rendered verbatim bring their own `##` headings into the handoff and break its section structure

Spec §A fences every verbatim body with a fence longer than any backtick run in it; Test Plan 2 covers a `##` heading inside an input.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-09-28T19:40:02+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: The published fr-goal explainer lists what the executor is given and needs an update, but the spec does not plan one

Spec §D adds the 01-fr-goal explainer update and .html regeneration (or a stated owed note in the PR body).
