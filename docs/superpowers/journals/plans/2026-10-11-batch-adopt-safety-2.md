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

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-11T21:00:32+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · stop-report re-run command interpolates --checkout (and ids) unquoted (phase 1)

triage_batch_cmd.py stop report: a path with spaces gives a broken copy-paste command. Fix: shlex.quote.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-11T21:00:32+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · stop-report test lacks a negative case (phase 1)

Only the both-flags case was tested; an always-echoed --no-hold would silently un-hold a re-run.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-11T21:00:32+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · herdr _agent_cwd/_agent_session duplicate restart.py's reads; P1.T4.S3 outcome unrecorded (phase 1)

runner.py's helpers repeat restart.py:532/537.

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-10-11T21:00:32+00:00 phase=1 -->
### p1-review-1 · review · Phase 1 code review (phase 1)

Dispatched read-only reviewer checked R1-R4, R10 and the R9 flag echo against spec §A/§C, ran the adopt and herdr tests and the hold scenario. Raised p1-r1..p1-r3, all in scope; all fixed (shlex-quoted re-run args, negative stop-report test, agent_cwd/agent_session moved to fr_herdr._herdr and shared by runner and restart).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-11T21:00:32+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: stop-report re-run command interpolates --checkout (and ids) unquoted (phase 1)

Stop report quotes batch id, tab, branch and --checkout with shlex.quote.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-11T21:00:32+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: stop-report test lacks a negative case (phase 1)

Added test_the_stop_report_echoes_neither_flag_when_not_given.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-11T21:00:32+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: herdr _agent_cwd/_agent_session duplicate restart.py's reads; P1.T4.S3 outcome unrecorded (phase 1)

agent_cwd/agent_session now live in fr_herdr._herdr, used by both runner.list_sessions and restart; this is P1.T4.S3's refactor.
