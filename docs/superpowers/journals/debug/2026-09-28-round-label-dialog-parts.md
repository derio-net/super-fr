# Journal: 2026-09-28-round-label-dialog-parts

<!-- fr:journal kind=repro scope=debug id=a500b22d58b3 created=2026-09-28T13:54:00+00:00 -->
### a500b22d58b3 · repro · A round split across question dialogs labels every dialog (Round 1 of 1)

gh#766. Live run (Test Plan item 17 of the requirements-traceability spec): an 8-question round 1 was asked as two consecutive question calls (4+4), correct per fr-goal SKILL.md's ceil(N/4) rule. Every question in BOTH dialogs was prefixed (Round 1 of 1). Nothing marks the second dialog as a continuation, nor the first as incomplete — it reads as a repeat or a miscount.
