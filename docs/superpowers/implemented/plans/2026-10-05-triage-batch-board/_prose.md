# Triage batch board — implementation plan

Spec: `docs/superpowers/specs/2026-10-05-triage-batch-board-design.md`.

Three agentic phases, one per ask:

1. **Session capabilities** (R8, R9) — the skeleton. Live herdr focus fixtures
   first, then the two optional runner protocols beside `SessionCloser`, the
   herdr implementation, and `fr triage batch focus` in a new soft point
   `triage_kanban_cmd.py`. Ends with the jump command working from a shell.
2. **The board** (R1–R7, R10, R14, R15) — the pure model (`fr.triage.kanban`:
   columns, hints, cards), the pure page (`fr.triage.kanban_render`), and
   `fr triage board` with live session statuses. Ends with a browser check of
   every visual state the rows name.
3. **Freshness** (R11–R13) — the drive re-renders the board every `--yes`
   pass, `fr triage board --watch` for when no drive runs, the link from
   `triage.html`, and the `fr-triage` skill (both mirror generators).

Internal module names say `kanban` because "the board" already means
`triage.html` throughout `fr/triage`; the operator-facing names are
`fr triage board` and `board.html`, as decided.

Import direction: `fr.triage.kanban*` never import `fr_dispatch`;
`triage_kanban_cmd.py` is the third soft point and imports only
`triage_cmd`; `triage_batch_cmd` imports `write_board` from it, one way.
