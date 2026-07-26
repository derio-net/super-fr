# Journal: 2026-07-26-fr-goal-isolation-deadlocks

<!-- fr:journal kind=discovery scope=plan id=p1-d1 created=2026-07-26T15:37:40 phase=1 -->
### p1-d1 · discovery · decision() must assert exit 0 or every allow-test passes vacuously (phase 1)

First cut of test_hooks_phase_executor_guard.py returned None from decision() whenever stdout was empty. An ABSENT hook also produces empty stdout, so 7 of 13 tests 'passed' during the RED run against a file that did not exist. decision() now asserts returncode == 0 first; the RED run then failed all 13. Worth carrying to any future hook test in this repo.

<!-- fr:journal kind=discovery scope=plan id=p2-d1 created=2026-07-26T15:43:34 phase=2 -->
### p2-d1 · discovery · fr-goal SKILL.md was already at the hard 120-line cap (phase 2)

test_skill_validation.py::test_under_120_lines is a hard cap with no exemption, and fr-goal/SKILL.md sat exactly at 120. The §6 addition had to be paid for. Reclaimed by reflowing §1, §3, §6, §7, §8 to the ~92-char width the file already used on its longest lines — no content dropped — and by folding the new constraint into §6's existing paragraph instead of adding a standalone block. Back to exactly 120. Any future addition to this skill must budget the same way.

<!-- fr:journal kind=discovery scope=plan id=p2-d2 created=2026-07-26T15:43:34 phase=2 -->
### p2-d2 · discovery · The allowlist script needed TWO independent probes, not one (phase 2)

The original script had a single early exit (grep -q QUALIFIED). Adding the message repair under it would have reproduced the exact bug the file already documents: a probe satisfied by one surface reporting 'already done' for another. A hook whose case arm was already fixed would never get its message repaired. Restructured into two independently-probed repairs — case arm (fail-loud on anchor drift) and the Exempt: message (silent no-op when absent, since the message is the org hook's prose, not super-fr's to require). test_message_repaired_even_when_case_already_correct pins it.

<!-- fr:journal kind=finding scope=plan id=p3-f1 created=2026-07-26T15:46:24 phase=3 state=refuted -->
### p3-f1 · finding [refuted] · Plan step P3.T1.S2 asked for 'cd <base-repo-subdir> && fr isolation up' to stay DENIED — refuted (phase 3)

Written before the composition rule was worked through. `fr isolation up` from the base-repo cwd is ALREADY allowed today (the fr-isolation allowance is precisely the one permitted surface there), so denying the same command merely because it was preceded by a cd within the same repo would be arbitrary and would contradict the allowance it composes with. The fence that IS correct — and is what the test asserts — is that a cd back into the base repo does not launder a NON-fr command: test_cd_back_into_base_repo_still_denied uses `make`. Step ticked against the corrected behaviour.

<!-- fr:journal kind=discovery scope=plan id=p3-d1 created=2026-07-26T15:46:24 phase=3 -->
### p3-d1 · discovery · Ordering is load-bearing: different-repo allow must precede the fr-isolation allowance (phase 3)

If the rest-stripped `fr isolation down` match were evaluated before the different-repo exit, `cd <other-repo> && fr isolation down` would retire THIS repo's sentinel — silently ending a live pipeline in repo A from a command aimed at repo B. Putting the different-repo exit first means such a command never reaches the sentinel-clearing branch. Pinned by test_isolation_down_in_other_repo_does_not_clear_this_sentinel, which also re-asserts that repo A stays guarded afterwards.

<!-- fr:journal kind=discovery scope=plan id=p3-d2 created=2026-07-26T15:46:24 phase=3 -->
### p3-d2 · discovery · Guard tests need a live linked worktree or they pass for the wrong reason (phase 3)

The #341 self-heal fails OPEN and clears the sentinel when a successful `git worktree list` shows zero linked worktrees. A cross-repo fixture built from a bare `git init` therefore allows everything regardless of the change under test. TestCrossRepoReachability._setup adds a real linked worktree to repo A, and test_precondition_base_repo_still_denied fences the fixture by asserting the pipeline is genuinely guarding before any of the allow-assertions run.

<!-- fr:journal kind=finding scope=plan id=p4-f1 created=2026-07-26T15:53:15 phase=4 state=fixed -->
### p4-f1 · finding [fixed] · The §6 reflow split the token `fr journal add` across a line and broke a guard test (phase 4)

test_fr_goal_journal.py::test_journal_render_derives_pr_body asserts the literal substring 'fr journal add' is present in fr-goal/SKILL.md — a deliberate guard that the SKILL rewrite kept its load-bearing tokens. Rewrapping §6 to the wider column put 'fr journal' and 'add' on either side of a newline, so the substring vanished while the prose read identically. Caught by the full suite, not by the targeted runs. Fixed by rewrapping that clause so the token stays intact. Lesson for any future reflow of this file: the token guards are substring matches and do not tolerate a line break inside a backticked command.

<!-- fr:journal kind=discovery scope=plan id=p4-d1 created=2026-07-26T15:53:15 phase=4 -->
### p4-d1 · discovery · Two full-suite failures in this pod are environmental, not regressions (phase 4)

tests/unit/test_isolation_cmd.py (8 failures) needs FR_ISOLATION_TARGET unset to run devcontainer-mode assertions CI-style; this pod exports FR_ISOLATION_TARGET=worktree. tests/integration/test_bridge_project_id.py (2 failures) reads a real VK_DERIO_OPS_PROJECT_ID from the pod env, overriding the fixture's 'test-vk-project-id'. Both reproduce on the pre-change tree and both pass with those variables cleared: 1839 passed, 80 skipped, 90.36% coverage under the CI gate. Neither is caused by this PR, and neither affects GitHub Actions, which has neither variable set.
