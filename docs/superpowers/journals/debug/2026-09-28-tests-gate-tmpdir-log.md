# Journal: 2026-09-28-tests-gate-tmpdir-log

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-28T14:26:11+00:00 -->
### repro · repro · deliver tests= refused a $TMPDIR suite log that the orchestrator did write (#765)

Run 2026-09-28-feat-gh-759, session a913f2c8. One Bash call at 12:51:29Z ran `fr run advance …` (which opened step/deliver at 12:51:33Z) and then `uv run pytest … > $TMPDIR/full-suite.log 2>&1`, backgrounded; its task-notification reported completed at 12:55:48Z. `fr run resolve --record` at 12:56:02Z refused: 'no command of YOURS wrote it … since this unit opened at 12:51:33'. A rerun into a literal scratchpad path, as its own command at 12:56:10Z, passed.

<!-- fr:journal kind=ruled-out scope=debug id=h1-tmpdir-not-expanded created=2026-09-28T14:26:11+00:00 -->
### h1-tmpdir-not-expanded · ruled-out · Refuted: the gate does not expand an inherited $TMPDIR

The issue's diagnosis. `_resolve_target` drops an unresolved LEADING variable and matches the rest by trailing path segments, so `> $TMPDIR/full-suite.log`, its quoted form, the `fr isolation exec -- '…'` form and `| tee $TMPDIR/…` all match the resolved log (probed via `telemetry._writes`). Only `${TMPDIR}full-suite.log` (no slash) fails, and §8 does not spell it that way.
