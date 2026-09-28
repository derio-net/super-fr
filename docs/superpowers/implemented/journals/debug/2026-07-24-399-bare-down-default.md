# Journal: 2026-07-24-399-bare-down-default

<!-- fr:journal kind=repro scope=debug id=399-repro created=2026-07-24T17:20:14 -->
### 399-repro · repro · bare 'fr isolation down' errors on hardcoded vk-iso/work default

#399. Three sub-issues in isolation_cmd.py + isolation/types.py.

(1) PRIMARY: DEFAULT_BRANCH='vk-iso/work' (isolation_cmd.py:40) is the typer default for both up (L58) and down (L257). Bare 'fr isolation down' resolves to load_state(root,'vk-iso/work') -> None -> 'no isolation workspace for branch vk-iso/work', even when a real workspace for the cwd worktree exists. exec/restart/status/verify-merge already switched to branch:str|None + single-active resolution (#299 part 3); down was missed.

(2) status raises unhandled FileNotFoundError when worktrees dir gone. Suspect: repo default Path('.') -> repo.resolve() -> os.getcwd(); after down removes the worktree the shell sat in, cwd deleted -> FileNotFoundError.

(3) Bash-gate pipeline sentinel only cleared by 'down --all'. Bare 'down' of the LAST workspace leaves the sentinel -> guard still reports pipeline active.

<!-- fr:journal kind=root-cause scope=debug id=399-root-cause created=2026-07-24T17:22:27 -->
### 399-root-cause · root-cause · three independent root causes confirmed

(1) down's typer default is DEFAULT_BRANCH='vk-iso/work' (isolation_cmd.py:257); bare down resolves a phantom branch instead of the single active workspace. exec/restart/verify-merge already use branch:str|None + single-active resolution (#299 part 3); down was never migrated. No caller relies on bare down==vk-iso/work (skills always pass --branch or --all). up KEEPS DEFAULT_BRANCH.

(2) status (and every subcommand) does root = repo.resolve() with repo default Path('.'). After down removes the worktree the operator's shell sat in, cwd is deleted; Path('.').resolve() -> os.path.realpath -> os.getcwd -> FileNotFoundError, unhandled (exit 1, traceback). Confirmed via repro at isolation_cmd.py:209.

(3) Bare down never clears the pipeline sentinel. The bash guard clears it two ways but BOTH require the base-repo cwd: guard-observed clear (fr-isolation-guard.sh:87) is unreachable because the guard exits at L38 when down is run from the worktree cwd (the prescribed workflow); the self-heal (L101) only runs when cwd is the base repo too. clear_repo_sentinels exists but is wired only to down --all. Fix: down clears the repo sentinels eagerly when zero workspaces remain — the same eager path types.py already documents.

<!-- fr:journal kind=finding scope=debug id=399-fix created=2026-07-24T17:26:14 state=fixed -->
### 399-fix · finding [fixed] · down migrated to single-active resolution; _resolve_repo guards deleted cwd; eager sentinel clear

packages/fr/src/fr/commands/isolation_cmd.py:
(1) down's branch default vk-iso/work -> None; bare down resolves the single active workspace (mirrors exec/restart/verify-merge), errors listing candidates when >1, and echoes state.branch.
(2) new _resolve_repo(repo) converts the deleted-cwd FileNotFoundError into a clean IsolationError (exit 2); status/exec/restart/down/verify-merge routed through it.
(3) after a successful bare down, if list_states(root) is empty, clear_repo_sentinels(root) is called — the eager Python clear the bash guard can't do when down runs from the worktree cwd.

up KEEPS DEFAULT_BRANCH='vk-iso/work' (VK bridge default) — unchanged.

Tests (tests/unit/test_isolation_cmd.py): down_resolves_single_workspace_when_no_branch, down_no_branch_zero_workspaces_exits_2, down_no_branch_multiple_workspaces_exits_2, down_clears_sentinel_when_last_workspace_removed, down_keeps_sentinel_when_other_workspaces_remain, status_from_deleted_cwd_exits_2_not_traceback. All green; full isolation suite 172 passed. Two test_bridge_project_id failures are pre-existing/environment-dependent (fail on clean base, unrelated). Version bumped 3.14.0 -> 3.14.1.
