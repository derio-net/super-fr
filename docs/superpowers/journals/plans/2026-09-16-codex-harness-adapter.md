# Journal: 2026-09-16-codex-harness-adapter

<!-- fr:journal kind=discovery scope=plan id=f877b5ae69cf created=2026-09-16T07:58:19 phase=1 -->
### f877b5ae69cf · discovery · BSD sed: the plan's literal apply_patch extractor works unmodified on macOS (phase 1)

P1.T2.S1's sed pipeline was written without knowing which sed would run it. Verified on macOS (BSD sed, /usr/bin/sed) this session: all 5 extractor cases pass with the literal code, no GNU-vs-BSD workaround needed. The three constructs that could have differed all behave: -nE (ERE) is accepted; backreference \2 in the replacement works; and [[:space:]] includes carriage return, which is what makes the CRLF case (d) pass -- the trailing-whitespace sed strips the \r that (.+)$ greedily captures. Phase 3 (portability) can treat the extractor as BSD-clean and needs no dual-path sed here.

<!-- fr:journal kind=finding scope=plan id=8f9e812b02a2 created=2026-09-16T08:01:02 phase=1 state=fixed -->
### 8f9e812b02a2 · finding [fixed] · T3 case (b) was a weak RED: a missing script is indistinguishable from allow (phase 1)

P1.T3.S1 asked this to be recorded honestly. Both skeleton cases went RED because plugins/super-fr/hooks/codex/fr-isolation-required.sh did not exist (bash exits 127, 'No such file or directory'). Case (a) 'base clone denies' failed as 'assert None == deny' -- meaningful, since absent output can never be a deny. Case (b) 'valid worktree allows' failed ONLY on 'assert 127 == 0'; its second assertion (empty stdout) was vacuously satisfied, because a script that does not exist emits no stdout, which is byte-identical to an allow. At RED time (b) therefore proved nothing about allow-behaviour. FIXED at T4: with the script in place the pair runs 7 passed / rc=0, case (a) passes against the same binary, so that binary is demonstrably CAPABLE of denying and (b)'s silence is now a real allow. Read the pair together -- (b) is load-bearing only while (a) passes. Phase 2, which extends this file into the full matrix, must not add an allow-case without a paired deny-case against the same script.

<!-- fr:journal kind=finding scope=plan id=749ad7f5d79b created=2026-09-16T08:02:04 phase=1 state=open -->
### 749ad7f5d79b · finding [open] · Pre-existing red in tests/unit/test_workflow_check.py, unrelated to the Codex track (phase 1)

The unit suite is NOT green on this branch, and was not green before phase 1 touched anything: tests/unit/test_workflow_check.py::test_cli_all_fails_when_nothing_is_discoverable fails with 'assert 0 == 1' where the CLI printed 'fr-goal: ok' -- i.e. 'fr workflow check --all' still discovers fr-goal after the test monkeypatches both the shipped-workflows dir and the wheel-internal packaged_shipped_workflows_dir to None, so the 'nothing is discoverable' precondition no longer holds. Evidence it predates this phase: the baseline run was launched BEFORE any file was written (collection happens at t=0) and already reported '1 failed, 2776 passed, 80 skipped in 817.52s'; the same single test still fails in isolation in 0.82s; and phase 1 adds only NEW files (plugins/super-fr/hooks/codex/, lib/fr-apply-patch-paths.sh, two tests/unit/test_codex_*.py), none of which participate in workflow discovery. Phase 1's own gate is therefore '1 failed / 2783 passed' where the 1 is this. Do NOT chase it as Codex-track breakage, and do not let it mask a real regression -- later phases should diff the failure SET, not the pass/fail verdict.

<!-- fr:journal kind=discovery scope=plan id=be0e818a7970 created=2026-09-16T08:02:06 phase=1 -->
### be0e818a7970 · discovery · The unit suite takes ~14 minutes; budget for it (phase 1)

tests/unit runs 2777 tests in 817.52s (13m37s) on this Mac, far past a 600s command timeout -- the phase-1 baseline run had to be backgrounded. Later phases should run the full gate in the background and poll, or scope to the touched test files during the edit loop and run the full suite once at the end. A single codex test file runs in under 4s, so the fast inner loop is 'uv run pytest -q --no-cov tests/unit/test_codex_*.py'.

<!-- fr:journal kind=discovery scope=plan id=8bb001229ff1 created=2026-09-16T08:04:42 phase=1 -->
### 8bb001229ff1 · discovery · The cwd-join is load-bearing: proved ALLOW-vs-BLOCK against a real base clone (phase 1)

The spec (4.C, journal d7) calls the cwd-join the correctness trap, so phase 1 verified it directly rather than trusting the unit tests to notice. Built a throwaway fr-enabled BASE CLONE (devcontainer profile, no .fr-isolation marker) and asked the shared decision library the same question twice. Result: fr_isolation_decide_edit 'src/a.py' (apply_patch's repo-relative path, verbatim) returns ALLOW, and fr_isolation_decide_edit "$(fr_resolve_against $repo src/a.py)" returns BLOCK. So the gate's deny is genuinely produced by the join; without it every patch would be allowed while the hook looked healthy, and the phase-1 deny test would still be the only thing that failed. This also means the two skeleton tests are not vacuously passing. Phase 2: any new case must keep the join, and a regression here would present as an over-permissive gate, not as an error.
