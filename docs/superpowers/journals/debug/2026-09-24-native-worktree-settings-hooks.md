# Journal: 2026-09-24-native-worktree-settings-hooks

<!-- fr:journal kind=repro scope=debug id=2d16ecf68899 created=2026-09-24T21:23:44 -->
### 2d16ecf68899 · repro · claude --worktree on a default install creates a native worktree; fr's WorktreeCreate never runs

Walking worktree-traceability P7.T2.S2 on 2026-09-24 (Claude Code 2.1.281, fr 4.19.2). `claude --worktree demo` in super-fr created `<repo>/.claude/worktrees/demo` on branch `worktree-demo`. `fr isolation status` had no `wt/demo`, and the status line read 'no fr-isolation'. The plugin's `hooks.json` registers `WorktreeCreate` -> `${CLAUDE_PLUGIN_ROOT}/hooks/fr-worktree-create.sh`.

<!-- fr:journal kind=ruled-out scope=debug id=7e77e09ed1a8 created=2026-09-24T21:23:44 -->
### 7e77e09ed1a8 · ruled-out · The hook script is not broken

Invoked directly with `{name, cwd, session_id}`, `fr-worktree-create.sh` exits 0 and prints `~/.cache/fr/worktrees/super-fr/wt__probe` (`wt/probe`, session bound). The docs say a nonzero `WorktreeCreate` exit fails creation with no fallback, so a hook that ran and failed would have blocked the session. It was never invoked.

<!-- fr:journal kind=root-cause scope=debug id=68180169718d created=2026-09-24T21:23:45 -->
### 68180169718d · root-cause · Claude Code 2.1.281 does not invoke plugin-registered WorktreeCreate for --worktree; settings-registered hooks do fire

The same two scripts registered in `~/.claude/settings.json` (`bash ~/.claude/plugins/cache/derio-net--super-fr/super-fr/current/hooks/fr-worktree-{create,remove}.sh`) fired live. `claude --worktree demo2` landed in `~/.cache/fr/worktrees/super-fr/wt__demo2` (`wt/demo2`, container running, sessions=<the demo2 session id>), and `exit` removed the workspace and its container through `WorktreeRemove`. install.sh registers these hooks only via the plugin, so a default install never routes native worktree sessions into fr. Side cost: the session waits for a full devcontainer up before it starts.

<!-- fr:journal kind=finding scope=debug id=f-settings-hooks created=2026-09-24T21:28:18 state=fixed -->
### f-settings-hooks · finding [fixed] · install.sh registers the worktree hooks in settings.json; the create hook is serialized

install.sh now also registers `bash <cache>/super-fr/current/hooks/fr-worktree-{create,remove}.sh` under `hooks.WorktreeCreate` / `hooks.WorktreeRemove` in `~/.claude/settings.json`. It strips every entry naming fr's scripts first and then appends, so reinstalls converge instead of duplicating, and another tool's hook on the same event is kept. `--uninstall` removes exactly fr's entries and drops an event left empty. Because the hook can now be registered twice, `fr-worktree-create.sh` serializes `fr isolation up` per repo+branch with an atomic mkdir lock. The lock reclaims a dead holder and gives up after 15 minutes. Pinned red-first: `tests/integration/test_install_worktree_settings_hooks.py` (4 red, then green) and `test_hooks_worktree.py::test_two_concurrent_invocations_do_not_overlap`. That test was first vacuous: piped stdin serialized the two runs until it was fed from a file. With the file it went red (OVERLAP), then green.

<!-- fr:journal kind=finding scope=debug id=f-corpus-floor created=2026-09-24T21:34:57 state=fixed -->
### f-corpus-floor · finding [fixed] · The dispatch-lint corpus floor assumed at least 3 live plans; archiving a finished plan broke it

Archiving worktree-traceability (required, or test_no_merged_but_unarchived_plans fails on main after merge) left 2 live plans. test_every_corpus_root_contributes demanded a flat MIN_PLANS_PER_ROOT=3 per root, so the two tripwires contradicted each other whenever few plans are in flight. The floor is now min(3, plan dirs present): a renamed root still fails on is_dir (mutation-checked by moving plans/ aside), and every live plan must still be read.

<!-- fr:journal kind=review scope=debug id=0ff25bee5b7b created=2026-09-24T21:47:28 -->
### 0ff25bee5b7b · review · Independent review: 2 important findings fixed, 2 minor fixed, 1 noted

A separately dispatched reviewer (static reading, no shell) raised: **(1) fixed:** WorktreeRemove is double-registered too but had no lock. fr-worktree-remove.sh now serializes per worktree path; its concurrency test went red (OVERLAP) and then green. **(2) fixed:** an unquoted path in the registered command breaks under a HOME containing a space. The command is now bash \"<path>\", pinned by a HOME-with-space test using shlex. **(3) fixed:** the strip filter aborted on a group without a hooks array; such groups are now left untouched (test). **(4) fixed:** it deleted an intentionally empty hooks object; that step is dropped (test). **(5) fixed:** trap is set before the pid write in the create hook. Not fixed: a HOME containing a double quote or \$ would still break the command, judged out of scope. The corpus-floor change was judged sound.
