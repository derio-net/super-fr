# Journal: 2026-10-06-run-evidence-witness

<!-- fr:journal kind=repro scope=debug id=repro-999 created=2026-10-06T08:19:53+00:00 -->
### repro-999 · repro · capture-script witness reads uv run --with value as the program (#999)

_program(["uv","run","--with","pyyaml","python","shots.py"]) returns [uv, pyyaml]; _executes(..., shots.py) is False. The first non-flag operand after uv run is the --with VALUE, not the program.

<!-- fr:journal kind=repro scope=debug id=repro-1002 created=2026-10-06T08:21:12+00:00 -->
### repro-1002 · repro · implement-phase refuses a suite log whose writer self-detached with & (#1002)

Real case (run 2026-10-05-feat-batch-triage-pages-goal, phase 2 executor): Bash run_in_background=true with command "cd <wt> && (uv run pytest ... > $TMPDIR/p2-suite.log 2>&1; echo exit=$? >> $TMPDIR/p2-suite.log) > /dev/null 2>&1 & echo started". The trailing & detaches the suite from the tool call, so the harness notice (status completed) is queued ~0.4s after issue, before the launch ack. wrote_since closes the window there; the log mtime (8.5 min later) falls outside every window and evidence.tests is refused. A plain run_in_background (no &) IS witnessed via the notice (gh#594/#693); OpenCode closes a & detach via _seen_exit (gh#719); the Claude Code reader has no equivalent.

<!-- fr:journal kind=root-cause scope=debug id=rc-1002 created=2026-10-06T08:21:47+00:00 -->
### rc-1002 · root-cause · Claude Code wrote_since ignores self-detached writers

telemetry.wrote_since never consults _detaches: a writer that backgrounds itself with & gets the window of its launcher (ack or immediate notice), never the suite. observed.py applies _detaches/_seen_exit only on the OpenCode path.
