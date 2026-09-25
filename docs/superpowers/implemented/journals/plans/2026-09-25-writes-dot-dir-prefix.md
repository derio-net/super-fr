# Journal: 2026-09-25-writes-dot-dir-prefix

<!-- fr:journal kind=discovery scope=plan id=4c9def11ec0a created=2026-09-25T00:47:45 phase=1 -->
### 4c9def11ec0a · discovery · no-refactor-because P1.T2 (phase 1)

A one-line .gitignore entry plus a scripted version bump. Neither has code to refactor.

<!-- fr:journal kind=decision scope=plan id=4918d510333f created=2026-09-25T00:48:07 phase=1 -->
### 4918d510333f · decision · Phase 1 dispatched untiered (phase 1)

The mechanical tier is unbound (fr models resolve prints nothing). Per operator decision d2, the untiered fr-phase-executor runs on the session model.

<!-- fr:journal kind=review scope=plan id=rv1 created=2026-09-25T00:52:04 phase=1 -->
### rv1 · review · Phase 1 code review (independent reviewer): no findings (phase 1)

Reviewed b263e642 against spec §2 and the plan. Edge cases traced by hand: len(parts)>len(log.parts), '.'-only, '..'-only, mid-path '..', tee -a, quoted targets. The tests pin every §2 case through both > and tee -a, plus one end-to-end test through orchestrator_wrote_since. Diff stat was checked by the orchestrator: 18 files, all in the plan's files: set or acceptance/plan artifacts.
