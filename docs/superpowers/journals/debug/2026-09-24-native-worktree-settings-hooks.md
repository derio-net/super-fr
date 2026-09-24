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
