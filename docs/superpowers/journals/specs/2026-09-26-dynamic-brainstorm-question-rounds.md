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
