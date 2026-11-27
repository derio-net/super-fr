# Split the free functions out of `isolation/local.py`

Four phases, one per new module, in dependency order (runner and reap are leaves; branchrefs
needs runner; landing needs all three). Each phase is a pure move: add the new module to the
forge-argv guard (red), move the group byte-identical (green), migrate every caller and lower
`local.py`'s budget (refactor). The last phase adds the no-import-of-local guard, settles the
budget and moves the `reviewed` stamps of the seven docs pages that cover edited paths.

No behaviour changes; tests change only their import lines. `_UP_REMEDY` and
`_FR_OWNED_EXCLUDES` stay in `local.py` beside the class that reads them.
