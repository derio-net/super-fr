# Journal: 2026-09-28-question-round-order

<!-- fr:journal kind=repro scope=debug id=764c1debe11a created=2026-09-28T18:46:21+00:00 -->
### 764c1debe11a · repro · A split round's question calls go out in parallel; the operator sees the last part first

On 2026-09-28, six triage batches (fr 4.29.7, Claude Code) reached fr-goal's round-1 gate. Every round with >4 questions issued its AskUserQuestion calls in ONE assistant message; Claude Code displays the last dialog first, so e.g. requirements-gate's operator first saw '(Round 1 · questions 5–5 of 5)'. Two sessions also read the per-call a–b label as a per-question sliding range (1–4, 2–4, 3–4, 4–4). Source: gh#783. Repro is the prose itself: plugins/super-fr/skills/fr-goal/SKILL.md §1 'Harness — questions' says 'ceil(N/4) CONSECUTIVE calls, back-to-back' with no instruction to wait for an answer, and a per-call 'a–b' label on a per-question surface.

<!-- fr:journal kind=ruled-out scope=debug id=21baff7ec6bc created=2026-09-28T18:46:23+00:00 -->
### 21baff7ec6bc · ruled-out · resolve's round counter does not depend on the label or on calls sharing a message

answered_rounds_since (fr/run/telemetry.py) groups consecutive QUESTION_TOOL tool_uses across assistant records; user tool_result records and text turns never close a round, only a non-question, non-progress-tracking tool_use does. test_a_round_counts_when_any_of_its_calls_was_answered already chains call→answer→call as ONE round. The only label text resolve reads is the substring 'a 2nd round may follow' (run_cmd.ANNOUNCEMENTS), matched in any question text of round 1. So sequential calls and a per-question label need no code change.

<!-- fr:journal kind=root-cause scope=debug id=c0b529d429c9 created=2026-09-28T18:46:25+00:00 -->
### c0b529d429c9 · root-cause · fr-goal §1's split rule says 'back-to-back', never 'wait for the answer', and gives a per-call label to per-question tabs

'ceil(N/4) CONSECUTIVE calls, back-to-back with no other tool call between them' is satisfied by parallel calls in one message, which Claude Code shows last-first — defeating 'interpretations of the input come first'. The 'a–b names each call's part' label is attached to a call but written into each question's text, so agents disagree on whose range it is, and a lone last question reads '5–5 of 5'. The greedy 4+1 split also leaves a singleton call. fr-brainstorming defers to fr-goal and does not restate the rule.

<!-- fr:journal kind=finding scope=debug id=8d7e4b916051 created=2026-09-28T18:53:00+00:00 state=fixed -->
### 8d7e4b916051 · finding [fixed] · fr-goal §1 rewritten: sequential, evenly split calls; one label per question

plugins/super-fr/skills/fr-goal/SKILL.md §1 + both mirrors: calls are SEQUENTIAL (never more than one question call per message, each only after the previous call is answered), split evenly (5 → 3 + 2), labelled (Round K · question i of N) per question; the Hermes/OpenCode prose fallback uses the same label. Pinned red-first by tests/unit/test_tripwire_fr_goal_question_rounds.py (test_fr_goal_asks_a_split_round_in_order, test_fr_goal_drops_the_parallel_split_wording — 33 failures before the fix). resolve unchanged; the new label and sequential transcript shape are pinned by test_run_question_rounds.py::test_the_verdict_table (gh#783 cases) and test_run_telemetry.py::test_sequential_question_calls_each_answered_before_the_next_are_one_round. fr-brainstorming defers to fr-goal and states no split rule, so it is untouched.
