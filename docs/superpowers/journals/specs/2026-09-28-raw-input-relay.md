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
