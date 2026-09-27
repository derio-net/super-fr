# Journal: 2026-09-27-opencode-xdg-data-home

<!-- fr:journal kind=repro scope=debug id=574cbe9b791a created=2026-09-27T19:27:44+00:00 -->
### 574cbe9b791a · repro · XDG_DATA_HOME-set OpenCode run: deliver refuses a valid suite log

gh#740. With XDG_DATA_HOME set and FR_OPENCODE_DB unset, OpenCode writes sessions to $XDG_DATA_HOME/opencode/opencode.db, but OpenCodeReader.database() resolves ~/.local/share/opencode/opencode.db. _opencode_wrote_since opens that (readable, wrong) db, finds no matching top-level bash part, returns [] and deliver refuses: 'no command of YOURS wrote it'. Repro in unit form: OpenCodeReader().database({'XDG_DATA_HOME': d}) != d/opencode/opencode.db; and orchestrator_wrote_since over a db with no part since the unit opened returns [] instead of None.
