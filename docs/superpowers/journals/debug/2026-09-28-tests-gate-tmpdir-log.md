# Journal: 2026-09-28-tests-gate-tmpdir-log

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-28T14:26:11+00:00 -->
### repro · repro · deliver tests= refused a $TMPDIR suite log that the orchestrator did write (#765)

Run 2026-09-28-feat-gh-759, session a913f2c8. One Bash call at 12:51:29Z ran `fr run advance …` (which opened step/deliver at 12:51:33Z) and then `uv run pytest … > $TMPDIR/full-suite.log 2>&1`, backgrounded; its task-notification reported completed at 12:55:48Z. `fr run resolve --record` at 12:56:02Z refused: 'no command of YOURS wrote it … since this unit opened at 12:51:33'. A rerun into a literal scratchpad path, as its own command at 12:56:10Z, passed.
