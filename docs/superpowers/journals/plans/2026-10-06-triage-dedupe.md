# Journal: 2026-10-06-triage-dedupe

<!-- fr:journal kind=decision scope=plan id=one-phase created=2026-10-06T07:49:15+00:00 -->
### one-phase · decision · One agentic phase: one ask, small surfaces read against one spec

Model, engine, check, board, driver and skill are one reviewable ask (triage finds and records duplicates); a second phase would add a fixed executor/reviewer round trip and a skeleton task for no review benefit.

<!-- fr:journal kind=discovery scope=plan id=skill-120-line-cap created=2026-10-06T08:27:13+00:00 phase=1 -->
### skill-120-line-cap · discovery · fr-triage SKILL.md sat exactly at the 120-line cap (phase 1)

tests/unit/test_skill_validation.py caps every SKILL.md at 120 lines and fr-triage was already at 120, so the dedupe teaching had to be paid for by joining wrapped paragraphs (no words dropped) and putting the example row on one flow line.

<!-- fr:journal kind=discovery scope=plan id=kanban-phrase-table created=2026-10-06T08:27:13+00:00 phase=1 -->
### kanban-phrase-table · discovery · A new ActionKind needs a phrase in triage/kanban.py (phase 1)

kanban._ACTION_PHRASES is indexed by every ActionKind (test_every_action_kind_has_a_phrase), so adding dedupe to the driver needed a phrase there; the action names no batch and is never a card hint.

<!-- fr:journal kind=discovery scope=plan id=dedupe-fixture-states created=2026-10-06T08:27:13+00:00 phase=1 -->
### dedupe-fixture-states · discovery · The calibration capture is mostly closed issues (phase 1)

594/607/631/640/647/724/725 are closed on the forge today; the test loads every captured issue as open, since the engine compares open issues only and the capture is of text, not state.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-10-06T08:27:13+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

Task 6 is skill prose, mirrors, fragment and matrix; there is no code to restructure (the 120-line skill cap was met by joining wrapped lines, content unchanged).
