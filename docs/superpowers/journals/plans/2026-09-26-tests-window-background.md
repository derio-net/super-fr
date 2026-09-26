# Journal: 2026-09-26-tests-window-background

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-26T15:07:27 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

RED-only task (tests); nothing to clean

<!-- fr:journal kind=finding scope=plan id=r1 created=2026-09-26T15:11:05 phase=1 state=open review_scope=in -->
### r1 · finding [open] (reviewer: in scope) · No end-to-end test through _verify_tests_log for the background case (phase 1)

Reviewer af94f054d5c0bb13d: tests stopped at orchestrator_wrote_since.

<!-- fr:journal kind=finding scope=plan id=r2 created=2026-09-26T15:11:05 phase=1 state=open review_scope=in -->
### r2 · finding [open] (reviewer: in scope) · Vacuous variable case '/y/$L' expected False for the wrong reason (phase 1)

L is assigned, path just differs.

<!-- fr:journal kind=finding scope=plan id=r3 created=2026-09-26T15:11:05 phase=1 state=open review_scope=in -->
### r3 · finding [open] (reviewer: in scope) · Refusal variants covered only for string content; is_error ack untested (phase 1)

Text-block shape only covered for success.

<!-- fr:journal kind=finding scope=plan id=r4 created=2026-09-26T15:11:05 phase=1 state=open review_scope=in -->
### r4 · finding [open] (reviewer: in scope) · Exit-code regex scanned the whole notification, spec says the summary (phase 1)

Closed-direction only, but off-spec.

<!-- fr:journal kind=finding scope=plan id=r5 created=2026-09-26T15:11:05 phase=1 state=open review_scope=out -->
### r5 · finding [open] (reviewer: out of scope) · _ASSIGNMENT is purely syntactic (echo L=..., env-prefix, subshell can resolve) (phase 1)

Same forgery class as `echo ok > log`, already the gate's stated limit.

<!-- fr:journal kind=finding scope=plan id=r6 created=2026-09-26T15:11:05 phase=1 state=open review_scope=out -->
### r6 · finding [open] (reviewer: out of scope) · OpenCode & detach still has a zero-length window (phase 1)

Spec non-goal; no completion event; follow-up.

<!-- fr:journal kind=review scope=plan id=phase1-review created=2026-09-26T15:11:05 phase=1 -->
### phase1-review · review · independent review of phase 1: 6 findings (4 in, 2 out) (phase 1)

Reviewer af94f054d5c0bb13d verified §3.A and §3.B behaviour, tripwire and forgery surface; raised r1-r6.

<!-- fr:journal kind=finding scope=plan id=r1-resolved created=2026-09-26T15:11:05 phase=1 state=fixed resolves=r1 -->
### r1-resolved · finding [fixed] · resolves r1: No end-to-end test through _verify_tests_log for the background case (phase 1)

test_a_backgrounded_suite_passes_the_deliver_gate_end_to_end drives _verify_tests_log: accepted inside the window, refused after.

<!-- fr:journal kind=finding scope=plan id=r2-resolved created=2026-09-26T15:11:05 phase=1 state=fixed resolves=r2 -->
### r2-resolved · finding [fixed] · resolves r2: Vacuous variable case '/y/$L' expected False for the wrong reason (phase 1)

Replaced with '/y/$UNSET/t.log'.

<!-- fr:journal kind=finding scope=plan id=r3-resolved created=2026-09-26T15:11:05 phase=1 state=fixed resolves=r3 -->
### r3-resolved · finding [fixed] · resolves r3: Refusal variants covered only for string content; is_error ack untested (phase 1)

Refusal variants now parametrized over text blocks too. The is_error ack stays covered only by code reading; foreground is_error tests already pin that a failed command yields no window.

<!-- fr:journal kind=finding scope=plan id=r4-resolved created=2026-09-26T15:11:05 phase=1 state=fixed resolves=r4 -->
### r4-resolved · finding [fixed] · resolves r4: Exit-code regex scanned the whole notification, spec says the summary (phase 1)

Scoped to <summary>; test_exit_code_text_outside_the_summary_does_not_reject_a_success.

<!-- fr:journal kind=finding scope=plan id=r5-resolved created=2026-09-26T15:11:05 phase=1 state=open resolves=r5 out_of_scope=true -->
### r5-resolved · finding [out-of-scope] · resolves r5: _ASSIGNMENT is purely syntactic (echo L=..., env-prefix, subshell can resolve) (phase 1)

The gate's documented forgery limit; this change adds no new class.

<!-- fr:journal kind=finding scope=plan id=r6-resolved created=2026-09-26T15:11:05 phase=1 state=open resolves=r6 out_of_scope=true -->
### r6-resolved · finding [out-of-scope] · resolves r6: OpenCode & detach still has a zero-length window (phase 1)

Also spec-review s2; OpenCode has no completion event and needs its own design.

<!-- fr:journal kind=review scope=plan id=phase1-review-opus created=2026-09-26T23:50:23 phase=1 -->
### phase1-review-opus · review · independent code review on claude-opus-5-5 (fresh context): 8 findings (7 in, 1 out) (phase 1)

Reviewer a5d182fc33b6777d7 (opus). Re-run because phase1-review ran on Sonnet. Checked against ~240 real notifications; F1/F2 were high severity.

<!-- fr:journal kind=finding scope=plan id=o1 created=2026-09-26T23:50:56 phase=1 state=open review_scope=in -->
### o1 · finding [open] (reviewer: in scope) · F1 queued-attachment task-notification shape never seen (Opus code review) (phase 1)

45 of ~240 real notifications arrive as attachment/queued_command and got no window. Fixed.

<!-- fr:journal kind=finding scope=plan id=o2 created=2026-09-26T23:50:56 phase=1 state=open review_scope=in -->
### o2 · finding [open] (reviewer: in scope) · F2 timeout-moved foreground command not recognised as background (Opus) (phase 1)

36 real cases; keyed on toolUseResult.backgroundTaskId (set on 187/187 real acks). Fixed; also closes F6.

<!-- fr:journal kind=finding scope=plan id=o3 created=2026-09-26T23:50:57 phase=1 state=open review_scope=in -->
### o3 · finding [open] (reviewer: in scope) · F3 assignment scan resolves variables the shell would not (Opus) (phase 1)

Prefix assignment, quoted text, here-doc. Fixed: command-start only.

<!-- fr:journal kind=finding scope=plan id=o4 created=2026-09-26T23:50:58 phase=1 state=open review_scope=in -->
### o4 · finding [open] (reviewer: in scope) · F4 quadratic _NOTIFIED_STATUS regex (Opus) (phase 1)

Replaced with a linear pattern.

<!-- fr:journal kind=finding scope=plan id=o5 created=2026-09-26T23:50:58 phase=1 state=open review_scope=in -->
### o5 · finding [open] (reviewer: in scope) · F5 exit code taken from model-written summary text (Opus) (phase 1)

Now the trailing (exit code N) only.

<!-- fr:journal kind=finding scope=plan id=o6 created=2026-09-26T23:50:59 phase=1 state=open review_scope=in -->
### o6 · finding [open] (reviewer: in scope) · F7 test gaps, weak assertion, fixtures not captured (Opus) (phase 1)

Added attachment, timeout-ack, misresolution, duplicate, ordering, sidechain cases; strengthened assertion; 12 new tests confirmed red on the old code.

<!-- fr:journal kind=finding scope=plan id=o7 created=2026-09-26T23:51:00 phase=1 state=open review_scope=in -->
### o7 · finding [open] (reviewer: in scope) · F8/F9 stale docstring; a background window can span the whole run (Opus) (phase 1)

Docstring updated with the window-length limit.
