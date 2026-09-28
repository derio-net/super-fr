# Journal: 2026-09-28-round-label-dialog-parts

<!-- fr:journal kind=repro scope=debug id=a500b22d58b3 created=2026-09-28T13:54:00+00:00 -->
### a500b22d58b3 · repro · A round split across question dialogs labels every dialog (Round 1 of 1)

gh#766. Live run (Test Plan item 17 of the requirements-traceability spec): an 8-question round 1 was asked as two consecutive question calls (4+4), correct per fr-goal SKILL.md's ceil(N/4) rule. Every question in BOTH dialogs was prefixed (Round 1 of 1). Nothing marks the second dialog as a continuation, nor the first as incomplete — it reads as a repeat or a miscount.

<!-- fr:journal kind=root-cause scope=debug id=8432834a7811 created=2026-09-28T13:54:02+00:00 -->
### 8432834a7811 · root-cause · fr-goal §1 mandates the round label but never the dialog part

plugins/super-fr/skills/fr-goal/SKILL.md §1 says every round-1 question text starts (Round 1 of 2) or (Round 1 of 1); the Claude Code questions clause splits a round of N into ceil(N/4) consecutive calls. No sentence composes the two: the agent followed the prose exactly, so every dialog carries the identical label. The gate is not involved: run_cmd.py's design-risk check is a case-insensitive substring match (ANNOUNCEMENT = 'round 1 of 2') over any round-1 question text, so a part suffix AFTER the round token stays compatible. Hermes/OpenCode ask in one reply, so they have no dialogs to number.

<!-- fr:journal kind=hypothesis scope=debug id=42ec13f6a3c7 created=2026-09-28T14:07:58+00:00 -->
### 42ec13f6a3c7 · hypothesis · Operator: drop the 'of N' round count — it is a forecast, not a fact

First fix (a part suffix after '(Round 1 of N') rejected by the operator before commit: 'of 1' can become 2 (operator-request) and 'of 2' is a ceiling that may resolve rounds: 1, so the count is never reliably accurate. Decision: labels are '(Round K · questions a–b of N)' — the part count is exact because a round's questions are collected before the first is asked — and a round-1 label adds '· a 2nd round may follow' IFF the agent forecasts a design-risk round 2. The gate's design-risk announcement check moves to that phrase; the legacy 'round 1 of 2' is still accepted so a session begun under the old prose is not refused mid-upgrade. operator-request round 2 needs no announcement, unchanged.

<!-- fr:journal kind=finding scope=debug id=8d152a00fb8b created=2026-09-28T14:15:53+00:00 state=fixed -->
### 8d152a00fb8b · finding [fixed] · Round labels count only what is certain; the forecast is its own phrase

fr-goal SKILL.md §1 + Claude Code questions clause (and both mirrors): labels are (Round K · questions a–b of N); round 1 adds '· a 2nd round may follow' iff a design-risk round 2 is forecast; interpretation questions come first in a split round. run_cmd.py ANNOUNCEMENT -> ANNOUNCEMENTS ('a 2nd round may follow', legacy 'round 1 of 2'). Tests written red first: test_tripwire_fr_goal_question_rounds.py (dialog-part markers, no '(Round N of' label, new contract markers — 12 then 31 failures before the fix) and test_run_question_rounds.py (verdict rows for the split-round labels, the case-insensitive phrase, the legacy token, and a label without the forecast refused). Matrix rows fr-goal-second-round-announced-and-verified / fr-goal-contract-prose-two-rounds reworded, reports regenerated. Full suite: 6838 passed.
