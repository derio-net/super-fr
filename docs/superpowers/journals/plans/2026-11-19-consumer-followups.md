<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-consumer-followups

<!-- fr:journal kind=discovery scope=plan id=p1-gates-second-session-get created=2026-11-20T02:19:30+00:00 phase=1 -->
### p1-gates-second-session-get · discovery · The gates' session lookup is a second session.get beside the claim's, until the directory is cached (phase 1)

`execute.before` now calls `claimChild` (its own `session.get`) and then the
session-directory resolver (another `session.get`, once per session while it
succeeds, R4). `claim.test.ts`'s wired test asserted exactly one lookup; it now
pre-seeds `sharedSessionDirectories()` so every lookup left is the claim's, keeping
the assertion strict. Sharing one lookup between claim and the resolver was not
done: claim reads `parentID`/`agent`, the resolver `id`/`location`, and the spec
leaves the claim handler unchanged.

<!-- fr:journal kind=discovery scope=plan id=p1-isolation-login-pin created=2026-11-20T02:19:30+00:00 phase=1 -->
### p1-isolation-login-pin · discovery · P1.T6.S1(b) is a pin, not a red — the isolation lifecycle refuses a Gitea login page once T5 re-raises it (phase 1)

`test_isolation_forge_refusal.py::test_a_gitea_login_page_is_refused_by_name_not_read_as_main_or_no_pr`
passed as soon as `RealTeaClient` re-raised the login page (the lifecycle already
catches `FORGE_ERRORS`). Checked against the pre-T5 `real_teaclient.py`: both
parametrisations fail there (main / no PR), so the test does pin R7.

<!-- fr:journal kind=decision scope=plan id=p1-gate-tests-new-file created=2026-11-20T02:19:30+00:00 phase=1 -->
### p1-gate-tests-new-file · decision · The R1-R4 wiring tests live in a new test/session-gates.test.ts, not in index/wiring tests (phase 1)

They need two fr-enabled repos, a workspace of the second, a fake `gh` on PATH and a
sentinel armed directly for the session's repo; neither existing file's fixture has
that shape, and the existing gate tests stay unchanged (P1.T3.S1). The bun level
refs on the acceptance row are file-level, as every existing bun ref in the matrix is.

<!-- fr:journal kind=discovery scope=plan id=p1-nag-quiet-placement-flake created=2026-11-20T02:19:30+00:00 phase=1 -->
### p1-nag-quiet-placement-flake · discovery · nag.test.ts's quiet-placement case failed once under a loaded host and passed on rerun (phase 1)

"the nag's acceptance directory (R1, R26) > under the quiet placement the fragments
live where fr settings paths says" failed once in a full `bun test` run (263 ms) and
passed alone and in the next full run. Not touched by this change (nag is unchanged);
recorded in case it recurs in CI.

<!-- fr:journal kind=discovery scope=plan id=p1-full-suite-load-failures created=2026-11-20T02:19:30+00:00 phase=1 -->
### p1-full-suite-load-failures · discovery · The full suite went 10 failed / 16879 passed under host load 40-146; all 10 pass when rerun alone (phase 1)

Four sessions ran full suites at once (load average 40, peaking at 146 on 12 cores),
so the suite ran with FR_PYTEST_WORKERS=6 and took 2h39m. The 10 failures were the 9
tests of `tests/unit/test_isolation_agent_worktrees.py` (the sweep answered
`skipped` where `reaped`/`warned` was expected) and
`tests/integration/test_scenarios.py::test_placement_move_and_drift`. None of them
touches a file this phase changed. Rerun alone on the same code tree, all 20 tests of
those two targets passed (95 s). The full-suite log is the evidence as it ran; a
rerun on a quieter host, or CI, is needed for a green full-suite log.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-20T02:19:30+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

bind.ts's parentInfo is not identical to the resolver: it returns the session info and a child flag for bind's child rule (a child never rebinds its parent, spec §A), so only sessionDirectory() is shared, as before

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-20T02:19:30+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

one template line and its goldens

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-20T02:19:30+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

six identical two-line guards over one new predicate; the redirect text became one constant shared by the raise and the predicate, nothing else to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-20T02:19:30+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

one try/except around one forge call; the isolation side needed no code change

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t7 created=2026-11-20T02:19:30+00:00 phase=1 -->
### no-refactor-p1-t7 · discovery · no-refactor-because P1.T7 (phase 1)

docs, acceptance rows and the gate run only; no code to clean

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-20T02:25:22+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · execute.before and execute.after each ran an uncached session lookup on every tool call (phase 1)

index.ts resolved the session's directory in execute.before and execute.after for every
tool call. A failed lookup is uncached (R4), so a hanging session.get cost about 4 s per
call, not the 2 s spec Design §A promises. The after-hook lookup only matters for a
completed skill call (writePipelineSentinel arms on nothing else), and the before-hook
lookup only matters when a gate judges the call (shell, or a writing tool without
FR_BASE_OK=1).

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-20T02:25:22+00:00 phase=1 -->
### review-p1-1 · review · Phase 1 code review — one in-scope finding (p1-r1), fixed (phase 1)

An independent reviewer read spec R1-R7 and every changed file. It confirmed:
- the resolver is bounded on every path and never rejects;
- a failure is never cached and an id-mismatch answer is rejected;
- unbind stays in the plugin directory;
- the six tea sites stay fail-soft on non-login errors;
- the predicate matches both login forms and nothing else;
- Gate.default refuses with exit 2;
- every Gitea checkout persists no credential;
- fixtures use only RFC 2606 names;
- the docs claims hold.
It raised one finding, p1-r1, in scope. Suggested lens: errors, which the run already carries.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-20T02:25:22+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: execute.before and execute.after each ran an uncached session lookup on every tool call (phase 1)

A new gateSkips(event) holds the edit gate's skip rule in one place. execute.before now
looks the session up only for shell, or for a call the gate judges. execute.after looks it
up only for a completed skill call. The new test in session-gates.test.ts ("a call no gate
judges makes no session lookup") fails without the fix and passes with it. Full bun test
349/0; tsc clean.
