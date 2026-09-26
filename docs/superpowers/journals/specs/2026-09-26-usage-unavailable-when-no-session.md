# Journal: 2026-09-26-usage-unavailable-when-no-session

<!-- fr:journal kind=decision scope=spec id=placeholder-empty-session-id created=2026-09-26T15:04:03 -->
### placeholder-empty-session-id · decision · Placeholder entry uses session ''

Operator chose the empty session id (the convention readers already use for 'no session id given'); no schema change, no migration.

<!-- fr:journal kind=decision scope=spec id=placeholder-dropped-on-real-capture created=2026-09-26T15:04:03 -->
### placeholder-dropped-on-real-capture · decision · Later real capture drops the placeholder

Operator chose drop: _merge discards a session '' / 'no session found' entry once real sessions exist.

<!-- fr:journal kind=decision scope=spec id=first-resolve-unchanged created=2026-09-26T15:04:03 -->
### first-resolve-unchanged · decision · require_sessions path keeps skipping

Operator chose: only deliver/closeout/archive write the placeholder.
