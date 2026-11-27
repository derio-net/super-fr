```
packages/fr-dispatch/src/fr_dispatch/protocols.py
  + SessionActivity.session_background(items) -> frozenset[str]     # optional, beside SessionNotes
packages/fr-herdr/src/fr_herdr/runner.py
  + HerdrRunner.session_background      # idle/done tabs → claude panes → pane read → has_background_work
packages/fr/src/fr/triage/
  + waits.py        Party, Wait, wait_of()          # §A's 13 ordered rows, pure; never moves a column
  + dwell.py        Ledger/Entry/Interval (AwareDatetime), observe(clock in), load/store,
                    card_dwell, wave_time (Done left out)
  ~ model.py        LaneOwners (display-only, typos → fr_ignored_keys note); FACTS_SCHEMA 21
  ~ kanban.py       Card.wait, ColumnView.owners, build_board(background=)
  ~ kanban_render.py wait pill + span.wait-owners (lane and gated cards), dwell line,
                    "Time per wave" (scrolling table, cutoff-hidden)
  ~ state_ref.py    REF_FILES += dwell.json; OBSERVED_FILES exempt from fetch clashes
packages/fr/src/fr/commands/
  ~ triage_kanban_cmd.py  read_sessions → SessionReads.background; write_board:
                          load → build → observe → store only if writer
                          (driver, or no live drive.lock and no unexpired lease) → render
  ~ triage_batch_cmd.py / triage_drive_loop.py   pass writer=True
docs/explainers/fr-triage.md, fr-dispatch.md, docs/reference/dispatch-lifecycle.md,
docs/herdr-control-sessions.md   # waits, owners, dwell, SessionActivity, the pane read
```
