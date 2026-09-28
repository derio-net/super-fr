# Journal: 2026-09-28-question-round-order

<!-- fr:journal kind=repro scope=debug id=764c1debe11a created=2026-09-28T18:46:21+00:00 -->
### 764c1debe11a · repro · A split round's question calls go out in parallel; the operator sees the last part first

On 2026-09-28, six triage batches (fr 4.29.7, Claude Code) reached fr-goal's round-1 gate. Every round with >4 questions issued its AskUserQuestion calls in ONE assistant message; Claude Code displays the last dialog first, so e.g. requirements-gate's operator first saw '(Round 1 · questions 5–5 of 5)'. Two sessions also read the per-call a–b label as a per-question sliding range (1–4, 2–4, 3–4, 4–4). Source: gh#783. Repro is the prose itself: plugins/super-fr/skills/fr-goal/SKILL.md §1 'Harness — questions' says 'ceil(N/4) CONSECUTIVE calls, back-to-back' with no instruction to wait for an answer, and a per-call 'a–b' label on a per-question surface.
