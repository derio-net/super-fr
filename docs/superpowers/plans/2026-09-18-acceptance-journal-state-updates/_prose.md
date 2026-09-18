# Acceptance and journal state updates

Implement #429 with explicit create-vs-update commands. Phase 1 introduces
validated acceptance status/evidence transitions and keeps the committed report
set synchronized. Phase 2 introduces a journal finding state transition,
turning duplicate journal creates from a silent no-op into an actionable error,
and teaches shipped agent guidance to use the new commands.

The phases are sequential because the first is the mutation/report walking
skeleton and the second completes the analogous journal lifecycle.
