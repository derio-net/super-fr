# Journal: 2026-10-11-batch-adopt-safety-2

<!-- fr:journal kind=discovery scope=plan id=p1-scenario-origin-shim created=2026-10-11T20:56:14+00:00 phase=1 -->
### p1-scenario-origin-shim · discovery · adopt scenario needs a git shim for origin (phase 1)

fr requires `remote get-url origin` to look like the batch's forge repo, and `get-url` applies insteadOf, so an offline clone cannot satisfy both that and fetch. tests/scenarios/fixtures/triage-adopt/bin/git answers only that call; every other git call is the real git.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-10-11T20:56:14+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

RED-only task (tests added); nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-11T20:56:14+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

adopt_message and the plan/step wiring were written once, with _pr_ref hoisted above the plan so plan and send share it; nothing duplicated left

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-11T20:56:14+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

scenario, fragment and matrix move only; no production code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-11T20:56:14+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

no existing harness-mapping helper in fr_herdr.restart is reusable (it only checks for claude/opencode kinds in-line); runner.py gets one small _HARNESSES map
