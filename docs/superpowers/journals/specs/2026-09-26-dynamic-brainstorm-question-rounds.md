# Journal: 2026-09-26-dynamic-brainstorm-question-rounds

<!-- fr:journal kind=decision scope=spec id=d1-enforcement created=2026-09-26T12:35:23 -->
### d1-enforcement · decision · Enforcement: prose + record check

The brainstorm step record declares question rounds (questions: {rounds, trigger, reason}); fr run resolve verifies against the transcript where readable. Record kind bumps 1->2 with a stamp-only migration.

<!-- fr:journal kind=decision scope=spec id=d2-sizing created=2026-09-26T12:35:23 -->
### d2-sizing · decision · Sizing: per operator-owned decision, soft ceiling ~10

No numeric cap. Above ~10 questions the agent justifies or proposes splitting the goal. On Claude Code a round spans ceil(N/4) consecutive AskUserQuestion calls with no other tool call between. Prose only, not counted in code.

<!-- fr:journal kind=decision scope=spec id=d3-round-two created=2026-09-26T12:35:23 -->
### d3-round-two · decision · Round 2 asks only what round 1 opened; never a round 3

Each round-2 question names the round-1 answer or code finding behind it. Triggers: design-risk (announced as Round 1 of 2) or operator-request (asked in prose during round 1).

<!-- fr:journal kind=decision scope=spec id=d4-contract-prose created=2026-09-26T12:35:23 -->
### d4-contract-prose · decision · The fr-goal contract prose changes on every surface that states it

Operator, mid-brainstorm: 'you'll need to change the prose, as we are changing the fr-goal contract'. Spec §3.A.1 enumerates every surface (skill description, opening, touchpoints, §1, fr-brainstorming, explainer .md+.html, README) and Test Plan 6 pins it with a tripwire.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-26T12:42:45 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · No channel carries the record's `questions` declaration into `_gate_provenance` on the --record path

apply.py:855-867 passes only evidence/emitted/no_questions/reason to resolve_in_process (run_cmd.py:4166); _gate_provenance's `record` is fr.run.model.StepRecord (the cursor), not the record artifact that gains `questions`. The declaration would silently never reach the gate on the path fr-goal uses.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-26T12:42:45 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · render_template hardcodes `schema_version: 1`; the record bump to 2 would break every fresh template

template.py:54 is a literal; model.py:168-174 refuses schema_version != RECORD_SCHEMA_VERSION. After the bump every dispatched step's filled template would be refused.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-26T12:42:45 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · §3.A.1 cites fr-goal/SKILL.md:46-55 but the AskUserQuestion clause is at :58

Citation slip in the surface inventory.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-09-26T12:42:45 -->
### spec-review-1 · review · independent spec review: 3 findings

Dispatched fr-spec-reviewer checked the spec against decisions d1-d4 and the codebase (file:line for _clears_gate, _gate_provenance, operator_answered_since, StepRecord/_SECTION_FIELDS, record kind registry, run_provenance, artifacts/__init__, every §3.A.1 prose surface). Verdict table checked exhaustively. Raised s1 (declaration not threaded to the gate), s2 (template hardcodes schema_version 1), s3 (citation slip). All in scope.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-26T12:42:45 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: No channel carries the record's `questions` declaration into `_gate_provenance` on the --record path

§3.B now threads `questions: QuestionRounds | None` apply_record -> resolve_in_process -> _resolve_body -> _gate_provenance beside no_questions/reason, names the two StepRecord classes, and Test Plan 7 pins both paths.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-26T12:42:45 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: render_template hardcodes `schema_version: 1`; the record bump to 2 would break every fresh template

§3.B requires render_template to write RECORD_SCHEMA_VERSION instead of the literal; Test Plan 5 pins that every fr-goal step's rendered template parses.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-26T12:42:45 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: §3.A.1 cites fr-goal/SKILL.md:46-55 but the AskUserQuestion clause is at :58

Citation widened to 46-62 naming the harness clause at :58.
