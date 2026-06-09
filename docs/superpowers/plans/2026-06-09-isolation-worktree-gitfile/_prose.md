# Worktree-safe git-dir resolution for `fr isolation`

Spec: `docs/superpowers/specs/2026-06-09-isolation-worktree-gitfile-design.md`
(issue [#292](https://github.com/derio-net/super-fr/issues/292)).

## Why

`fr isolation` assumes `<repo_root>/.git` is a directory. In a linked git
worktree it is a *gitfile* (a `gitdir:` pointer), so `state_path(...).parent
.mkdir()` raises `NotADirectoryError`. That kills `up`/`exec`/`status`/`down`
whenever they run from inside a worktree — most painfully an ephemeral agent
worktree (`Agent(isolation: "worktree")`), where host `git`/`gh`/`cat` are also
refused by the fr-isolation guard hook, leaving no way to operate.

## Approach

Resolve the **shared** git dir via `git rev-parse --git-common-dir` instead of
hardcoding `<repo_root>/.git`. For a main checkout that returns `.git`
(identical behavior); for a linked worktree it returns the real shared
`<main>/.git`, which all worktrees of the repo share — the correct key for
isolation state (state is repo+branch, not per-worktree).

Two layers change:

1. **State path layer** (`types.py`, `migrate.py`) — a `_git_common_dir`
   helper backs `state_dir`/`_legacy_state_dir` and the migrate paths. This is
   the linchpin: the CLI's `exec`/`status`/`down` call the module-level state
   functions *directly* with cwd, so fixing them here makes state location
   worktree-invariant regardless of caller.

2. **Target layer** (`local.py`) — normalize `repo_root` to the main checkout's
   toplevel in `__init__`, so the persisted `IsolationState.repo_root`, the
   `.git` bind-mount, the worktree cache bucket, and `down`'s teardown cwd all
   key off the durable main checkout rather than the (possibly reaped) launch
   worktree.

## Phases

1. **State-path layer** — `_git_common_dir` + worktree-safe `state_dir`/
   `_legacy_state_dir` + `migrate.py`. TDD; existing main-path tests stay green.
2. **Target layer** — normalize `repo_root` to the main toplevel and mount the
   common `.git` dir; TDD an end-to-end `up`-from-worktree test.
3. **CI gate + version bump** — run the canonical ci.yml gate
   (`ruff`/`mypy`/`pytest` over `packages/ tests/`) and bump the patch version
   (resolve to the next free patch; in-flight 3.1.5 lives in another workspace).

## Non-goals

No change to the global `resolve_repo_root()`; normalization is confined to the
isolation Target. No bare-repo support. No on-disk state-format change.
