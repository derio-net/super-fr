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

<!-- fr:journal kind=root-cause scope=debug id=rc-999 created=2026-10-06T08:21:51+00:00 -->
### rc-999 · root-cause · _program treats a value-taking uv run flag value as the program

telemetry._program picks the first word not starting with - after uv run; --with/--python/--project etc. take a separate value word.

<!-- fr:journal kind=hypothesis scope=debug id=h-1002-notice created=2026-10-06T08:49:51+00:00 -->
### h-1002-notice · hypothesis · Subagent transcripts lack the background notice, so the #693 fix never reaches implement-phase

Ruled out: 182 of 184 subagent transcripts with a background ack carry a task-notification; the phase-2 one does too.

<!-- fr:journal kind=ruled-out scope=debug id=ro-1002-notice created=2026-10-06T08:49:55+00:00 -->
### ro-1002-notice · ruled-out · Missing notice in subagent transcripts

The notice was present, queued at 22:03:23.996 with status completed. The window closed early because the command itself detached with &, not because the notice was missing.

<!-- fr:journal kind=finding scope=debug id=fix-1002 created=2026-10-06T08:49:58+00:00 state=fixed -->
### fix-1002 · finding [fixed] · wrote_since closes a self-detached writer at the first later exit=0 of its log

telemetry.wrote_since now records every completed foreground Bash call and, for a writer that _detaches, appends (issued, seen) where seen = _seen_exit over those calls: the same stand-in OpenCode uses (gh#719). Pinned by tests/unit/test_run_witness_detached.py (failing first). Replayed against the real phase-2 executor transcript: base window ends 22:03:23.996, fixed reader adds one ending 22:12:01.229, covering the 510 s suite.

<!-- fr:journal kind=finding scope=debug id=fix-999 created=2026-10-06T08:50:00+00:00 state=fixed -->
### fix-999 · finding [fixed] · uv run walks its flags and skips the values of value-taking ones

_program delegates uv to _uv_run_program, which skips _UV_VALUE_FLAGS values (taken from uv run --help). Pinned by test_a_uv_run_flag_value_is_not_the_program and test_a_uv_run_flag_value_naming_the_script_is_not_a_run_of_it (failing first).

<!-- fr:journal kind=review scope=debug id=review-1 created=2026-10-06T09:28:26+00:00 -->
### review-1 · review · Independent adversarial review: no significant findings; low ones fixed

Separate-context reviewer (read-only). Verified: main_thread filter, poll-before-window, launch acks, first-exit-final, superset-only extension, notice-before-ack ordering, uv run regressions. Fixed: vacuous sidechain test replaced by a mixed main-thread/sidechain case; added foreground & writer, early poll, launch-ack and is_error poll cases; dead uv entry in _SUBCOMMAND_RUNNERS removed. Refuted: missing value flags (uv 0.10.11 uv run --help lists none beyond _UV_VALUE_FLAGS; hidden --python-preference added). Informational kept: the extension needs the suite to print its own exit=N line (noted in the code). Full suite on the final tree: 9015 passed, 105 skipped (host run; the 2 GB devcontainer OOM-killed xdist workers).
