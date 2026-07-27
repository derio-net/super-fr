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

<!-- fr:journal kind=finding scope=plan id=rev-f1 created=2026-07-26T15:56:16 phase=1 state=fixed -->
### rev-f1 · finding [fixed] · Review: the hook matched only tool_name 'Agent', inert on hosts spelling it 'Task' (phase 1)

Claude Code's subagent-dispatch tool is 'Agent' today and was 'Task' on older builds. A host on the old spelling would have installed a hook that never fires — silently reproducing the exact failure mode this hook exists to stop, and undetectably so, since an inert PreToolUse hook looks identical to a healthy one. Widened the hooks.json matcher to 'Agent|Task' and the script's tool_name check to accept both. No false-positive risk: the subagent_type check is what narrows. Pinned by test_legacy_task_tool_name_still_denied.

<!-- fr:journal kind=review scope=plan id=rev-r1 created=2026-07-26T15:56:16 phase=3 -->
### rev-r1 · review · Review: live end-to-end probe of the rewritten guard against real git repos (phase 3)

Ran the hook directly against two real git repos with a live sentinel and a live linked worktree, outside pytest: 'git status' in repo A denied; 'cd B && fr isolation up' allowed; 'cd B && rm -rf /' allowed (target scoping is by repo, not by command); 'cd B && fr isolation down' allowed AND repo A's sentinel survived, with the next 'git status' in A still denied; 'cd A/sub && make' denied; 'echo hi && cd B && ls' denied (non-leading cd). Matches the spec's §D contract on every case. bash -n clean on all three changed scripts; shellcheck unavailable in this pod (noted, not run).

<!-- fr:journal kind=finding scope=plan id=rev-f2 created=2026-07-26T17:37:23 phase=2 state=fixed -->
### rev-f2 · finding [fixed] · Review: the #420 carve-out never reached OpenCode or Hermes (phase 2)

Phase 2 fixed the three CLAUDE-CODE-ONLY prose surfaces (agents/fr-phase-executor.md description:, fr-goal SKILL.md §6, the org allowlist script) and regenerated the SKILL mirrors, so the sync tripwires stayed green — masking the real gap. Neither .opencode/ nor .hermes/ carries an agents/ tree, so the agent description: reaches NEITHER harness, and the hook is Claude-Code-only by construction. The surface that does reach all three is plugins/super-fr/rules/fr-isolation-required.md: install.sh copies it to ~/.claude/rules/, sync-opencode.py mirrors it to .opencode/instructions/, and sync-hermes.py assembles it into the ~/.hermes/SOUL.md managed block. Worse, that rule NAMES agent-worktree-default.md as its Agent-tool companion, so super-fr's own shipped rule was endorsing the harmful always-pass-the-flag default unqualified on every host. Added a 'Carve-out' section there plus the hand-maintained .claude/rules/ mirror (AGENTS.md flags it as the one file no script regenerates), and three new tripwire assertions — including one that reads the GENERATED mirrors, because the sync tripwires only prove mirror==source and would stay green for a rule that never mentioned the carve-out at all.

<!-- fr:journal kind=discovery scope=plan id=rev-d1 created=2026-07-26T17:37:23 phase=2 -->
### rev-d1 · discovery · Verified: neither #420 nor #421 needs a Hermes or OpenCode hook port (phase 2)

#420 — Hermes dispatches via delegate_task(goal, context) (hermes-agent-compat spec §3.4); there is no isolation argument, so the poisoned shape is unrepresentable, and .hermes/config.snippet.yaml has no delegate_task matcher to add one to. OpenCode's plugin gates only EDIT_TOOLS = {edit, write, patch, multiedit} (packages/fr-opencode-plugin/src/index.ts:10) and has no subagent-dispatch surface carrying a worktree flag. #421 — plugins/super-fr/hooks/hermes/fr-isolation-guard.sh is MARKER-based, not sentinel-based: it computes an effective_dir from a leading cd and delegates to fr_isolation_decide_cwd, which evaluates fr-enablement per-toplevel, so it never had a repo-A-scoped sentinel to be trapped by. 'cd <other-repo> && fr isolation up' also is not matched by its is_mutation() filter. OpenCode has no bash guard at all (a known gap recorded in AGENTS.md, not introduced here). So the hook ports are genuinely unnecessary; the RULE port was not, and was missing.

<!-- fr:journal kind=finding scope=plan id=rev-f3 created=2026-07-26T18:32:03 phase=3 state=fixed -->
### rev-f3 · finding [fixed] · Review (operator): the #421 target-scoped allowance was too broad — it dropped repo B's own isolation (phase 3)

Operator challenge: 'fr-isolation can now just cd ANYWHERE? What kind of isolation is that?' Partly a misread (the EDIT gate fr-isolation-required.sh is marker-based, session-independent and untouched, so edits in repo B's base clone were never allowed; and a cd into a non-repo dir was already denied) — but correct on the substance for BASH. The blanket 'different git repo -> exit 0' conflated two distinct claims: 'repo A's pipeline should stop gating repo B' (what #421 asks) and 'repo B's own isolation should be dropped' (which nothing asks). It allowed 'cd <other-fr-repo> && git commit' in an UN-ISOLATED base clone — exactly what fr-isolation prevents — and made the Claude bash guard WEAKER than its own Hermes sibling, which is marker-based. The shared lib's docstring already said 'Used by both the edit gate and the bash guard'; the Claude bash guard was the one that never sourced it. Fixed: the cd target is now handed to fr_isolation_decide_cwd. Allowed context (worktree / non-fr repo / valid marker / FR_BASE_OK) -> allow, so #421 is satisfied; blocked context -> repo B's discipline stands, and execution falls through to the fr-allowances so 'cd <repo-B> && fr isolation up' still works — a discipline, not a deadlock. The blocked-target deny also gets its OWN reason naming repo B, because emitting repo A's 'fr pipeline active' text there would misattribute the block and point at the wrong worktree, the same misleading-remedy failure #421 was filed about. 8 new tests (TestOtherRepoStillHonoursItsOwnIsolation); 49/49 guard tests green.

<!-- fr:journal kind=finding scope=plan id=rev-f4 created=2026-07-26T18:40:36 phase=3 state=fixed -->
### rev-f4 · finding [fixed] · Review (operator): 'what about non-fr repos, like $HOME/.ssh?' — a dotfiles $HOME leaked the key (phase 3)

Measured rather than argued. Two cases: (1) ~/.ssh NOT inside a git repo -- DENIED both before and after, because the cross-repo allowance requires the target to be a git repo. (2) $HOME IS a dotfiles git repo -- was DENIED before this PR, became ALLOWED after it. 'git init' in $HOME is common (the operator's own environment references .dotfiles), so ~/.ssh acquires a git toplevel, is not fr-enabled, and sailed through. A fix for a deadlock must not widen reach to a private key as a side effect. Root cause: I keyed the allowance on REPO IDENTITY ('is it a different repo') and then on fr_isolation_decide_cwd, which answers 'allowed' for any non-fr repo -- correct for the edit gate, which has no business in a repo that never opted into fr, and wrong as a DESTINATION test for exactly this reason. Fixed by keying on ISOLATION instead: new public fr_isolation_marker_valid in hooks/lib/fr-isolation-decision.sh, so the destination must be a genuine fr isolation workspace. Everything else falls through to the prefix loop and the fr-allowances, so 'cd <repo-B> && fr isolation up' still works -- #421's whole ask is REACHING repo B's isolation, never using its base clone. Also: a cd into another repo now suppresses sentinel retirement, so 'cd <other> && fr isolation down' cannot end this session's pipeline by action-at-a-distance. 9 new tests across TestSensitivePathsStayOutOfReach and the reframed cross-repo classes; 54/54 guard tests green.

<!-- fr:journal kind=discovery scope=plan id=rev-d2 created=2026-07-27T11:36:21 phase=3 -->
### rev-d2 · discovery · Scope check: fr-isolation does not protect ~/.ssh, and the last summary oversold the fix (phase 3)

Operator asked the same question twice, which was the signal that the first answer was too narrow. Measured all three paths: (1) 'cat ~/.ssh/id_ed25519' with NO pipeline sentinel -> ALLOWED (fr-isolation-guard.sh exits at '[ -f $sentinel ] || exit 0'); (2) Write ~/.ssh/authorized_keys -> ALLOWED by the edit gate; (3) same with a dotfiles $HOME -> ALLOWED. All three are BY DESIGN: the shipped rule's step 2 is 'Target file not in a git repo, or repo not fr-enabled -> allow'. So super-fr has never protected ~/.ssh; what rev-f4 fixed was one regression in one path (live pipeline + leading cd), and describing that as 'closed' overstated it. No code change is warranted -- fr-isolation answers 'is this fr work in an fr repo's base clone?' and nothing else, and it has no way to know what is sensitive on a given machine. What WAS warranted: a 'Scope -- what fr-isolation does NOT protect' section in the shipped rule, naming ~/.ssh and the dotfiles-$HOME case explicitly and pointing at permissions.deny in ~/.claude/settings.json as the mechanism that can actually stop it. Ships to all three harnesses via the rule mirrors. Operator's own settings.json currently has 'deny': [] -- flagged to them, not changed, since their harness config is outside this PR.
