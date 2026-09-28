# Journal: 2026-09-28-question-round-order

<!-- fr:journal kind=repro scope=debug id=764c1debe11a created=2026-09-28T18:46:21+00:00 -->
### 764c1debe11a · repro · A split round's question calls go out in parallel; the operator sees the last part first

On 2026-09-28, six triage batches (fr 4.29.7, Claude Code) reached fr-goal's round-1 gate. Every round with >4 questions issued its AskUserQuestion calls in ONE assistant message; Claude Code displays the last dialog first, so e.g. requirements-gate's operator first saw '(Round 1 · questions 5–5 of 5)'. Two sessions also read the per-call a–b label as a per-question sliding range (1–4, 2–4, 3–4, 4–4). Source: gh#783. Repro is the prose itself: plugins/super-fr/skills/fr-goal/SKILL.md §1 'Harness — questions' says 'ceil(N/4) CONSECUTIVE calls, back-to-back' with no instruction to wait for an answer, and a per-call 'a–b' label on a per-question surface.

<!-- fr:journal kind=ruled-out scope=debug id=21baff7ec6bc created=2026-09-28T18:46:23+00:00 -->
### 21baff7ec6bc · ruled-out · resolve's round counter does not depend on the label or on calls sharing a message

answered_rounds_since (fr/run/telemetry.py) groups consecutive QUESTION_TOOL tool_uses across assistant records; user tool_result records and text turns never close a round, only a non-question, non-progress-tracking tool_use does. test_a_round_counts_when_any_of_its_calls_was_answered already chains call→answer→call as ONE round. The only label text resolve reads is the substring 'a 2nd round may follow' (run_cmd.ANNOUNCEMENTS), matched in any question text of round 1. So sequential calls and a per-question label need no code change.
