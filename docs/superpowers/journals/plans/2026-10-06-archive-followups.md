# Journal: 2026-10-06-archive-followups

<!-- fr:journal kind=discovery scope=plan id=p1-wrapper-decorator created=2026-10-06T17:40:04+00:00 phase=1 -->
### p1-wrapper-decorator · discovery · follow-ups wired by a signature-preserving decorator, not an edited body (phase 1)

`archive_command` keeps its typer signature; `_with_followups` (functools.wraps) opens the MoveLog and runs `_after_moves` in a finally, so every entry mode and exit path is covered without touching the body. Typer follows __wrapped__.

<!-- fr:journal kind=discovery scope=plan id=p1-green-in-smoke created=2026-10-06T17:40:04+00:00 phase=1 -->
### p1-green-in-smoke · discovery · MoveLog/recording_moves landed with the T1 smoke commit (phase 1)

T1's stub was the real implementation (a few lines), so T2's RED test passed on first run; the RED for the seam is the import test in T1 and the CLI-level `_after_moves` spies in T3, which failed before the wrapper existed.
