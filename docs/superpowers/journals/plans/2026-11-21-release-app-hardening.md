<!-- fr:journal-schema=4 -->
# Journal: 2026-11-21-release-app-hardening

<!-- fr:journal kind=discovery scope=plan id=setup-script-test-stub-shell-gotchas created=2026-11-21T12:15:43+00:00 phase=1 -->
### setup-script-test-stub-shell-gotchas · discovery · Stub gh in tests: positional-parameter pattern removal and here-string temp files (phase 1)

In the stub, `${*##*/}` applies per positional parameter, so copy `$*` to a variable first. Write bodies are logged compacted (`jq -c`) so a multi-line body stays one log line.

<!-- fr:journal kind=decision scope=plan id=setup-script-require-waits-exit-0 created=2026-11-21T12:15:43+00:00 phase=1 -->
### setup-script-require-waits-exit-0 · decision · require step: a missing variable that step 4 already reported as waiting exits 0 (phase 1)

R14 exits 0 only for the release check. The Test Plan's pre-merge run reaches require with the variable still waiting for the merge, so that case prints the wait and exits 0. A missing environment secret, or a variable missing with no reported wait, still refuses (exit 1). With no key at hand the installation-repositories check is a printed settings URL rather than a blocking prompt, so a rerun with no stdin stays a no-op.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-21T12:15:43+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

read_json and the shared step helpers already served the app step; nothing else to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-21T12:15:43+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the environment body and its desired projection are constants compared with jq -S from the start

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-21T12:15:43+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

the variable step reuses read_json and act; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t8 created=2026-11-21T12:15:43+00:00 phase=1 -->
### no-refactor-p1-t8 · discovery · no-refactor-because P1.T8 (phase 1)

documentation only, no code to refactor
