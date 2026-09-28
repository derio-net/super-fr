# Journal: 2026-09-28-round-label-dialog-parts

<!-- fr:journal kind=repro scope=debug id=a500b22d58b3 created=2026-09-28T13:54:00+00:00 -->
### a500b22d58b3 · repro · A round split across question dialogs labels every dialog (Round 1 of 1)

gh#766. Live run (Test Plan item 17 of the requirements-traceability spec): an 8-question round 1 was asked as two consecutive question calls (4+4), correct per fr-goal SKILL.md's ceil(N/4) rule. Every question in BOTH dialogs was prefixed (Round 1 of 1). Nothing marks the second dialog as a continuation, nor the first as incomplete — it reads as a repeat or a miscount.

<!-- fr:journal kind=root-cause scope=debug id=8432834a7811 created=2026-09-28T13:54:02+00:00 -->
### 8432834a7811 · root-cause · fr-goal §1 mandates the round label but never the dialog part

plugins/super-fr/skills/fr-goal/SKILL.md §1 says every round-1 question text starts (Round 1 of 2) or (Round 1 of 1); the Claude Code questions clause splits a round of N into ceil(N/4) consecutive calls. No sentence composes the two: the agent followed the prose exactly, so every dialog carries the identical label. The gate is not involved: run_cmd.py's design-risk check is a case-insensitive substring match (ANNOUNCEMENT = 'round 1 of 2') over any round-1 question text, so a part suffix AFTER the round token stays compatible. Hermes/OpenCode ask in one reply, so they have no dialogs to number.
