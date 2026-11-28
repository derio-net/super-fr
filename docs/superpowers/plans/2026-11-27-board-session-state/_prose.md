# Batches page: who each card waits for, lane owners, time per column

Spec: `2026-11-27-board-session-state-design.md` (derio-net/super-fr#1731).

Two agentic phases. Phase 1 adds the derived wait (`fr/triage/waits.py`), the optional
`SessionActivity` protocol and its herdr implementation over
`restart.has_background_work`, and `lane_owners` in `.fr/triage.yaml` (facts schema 21),
rendered as a pill on the card and an owners line under each Needs-you header. Phase 2
adds the dwell ledger (`fr/triage/dwell.py`, `dwell.json` on the state ref with one
writer and a fetch that adopts the ref's copy), the card's dwell line and the "Time per
wave" section.

Phase 2 depends on phase 1 because the ledger records `Card.wait`. Columns never change:
`lanes.lane_of` and `kanban.column_of` stay the only column decision.
