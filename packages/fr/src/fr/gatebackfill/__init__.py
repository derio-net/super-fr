"""`fr gate backfill` — bring pre-v6 owed work into the gate lanes (spec 2026-11-01-gate-backfill).

Pure given a forge port, a git port and the clock, as `fr.debt` is: `model` (the plan file and
manifest), `candidates` (what is owed and under which gate), `delivery` (which merged PR
delivered it), `render` (the summary and the repo-file commands). The command is
`fr.commands.gate_cmd`'s `gate backfill`.
"""
