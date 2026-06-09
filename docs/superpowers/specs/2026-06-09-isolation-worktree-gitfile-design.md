# fr isolation: worktree-safe git-dir resolution

**Issue:** [#292](https://github.com/derio-net/super-fr/issues/292) — `fr isolation`
crashes with `NotADirectoryError` when run from inside a git worktree, because
`.git` there is a *gitfile* (a `gitdir:` pointer) rather than a directory.

**Scope decided (operator):** Robust/full — not just stop the crash, but make
`up`/`exec`/`status`/`down` work end-to-end when launched from inside a worktree
(the headline agent-reviewer scenario). Blast radius stays inside the isolation
layer.

## Problem

`packages/fr/src/fr/commands/common.py::resolve_repo_root()` resolves the repo
via `git rev-parse --show-toplevel`. In a **linked worktree** that returns the
*worktree's* toplevel, not the main checkout. Downstream code then assumes
`<repo_root>/.git` is a directory:

- `types.py::state_dir()` → `repo_root / ".git" / "fr" / "isolation"`
- `types.py::_legacy_state_dir()` → `repo_root / ".git" / "vk" / "isolation"`
- `migrate.py:97-98` → `repo_root / ".git" / {"vk","fr"} / "isolation"`
- `local.py:72` → `git_dir = self.repo_root / ".git"` (bind-mounted into the container)

In a worktree, `<worktree>/.git` is a regular **file**, so
`state_path(...).parent.mkdir(...)` raises
`NotADirectoryError: <worktree>/.git/fr/isolation`.

### Why each CLI verb is affected

The CLI calls the module-level state functions **directly** with `repo.resolve()`
(cwd by default), *not* through the Target:

- `exec`  → `load_state(repo.resolve(), branch)` (`isolation_cmd.py:74`)
- `status`→ `list_states(root)` / `load_state(root, branch)` (`:100`)
- `down`  → `load_state(root, branch)` (`:130`)
- `up`    → Target, but `LocalWorktreeDevcontainerTarget.up()` ends in
  `save_state(...)` which hits `state_dir()` (`local.py:93`)

So `state_dir`/`_legacy_state_dir` must be worktree-safe regardless of caller —
this is the linchpin fix.

### Second, subtler bug (robustness)

Even once the crash is gone, `up` from a worktree stores
`IsolationState.repo_root = <the launch worktree>`. `down` later uses
`state.repo_root` as the cwd for `git worktree remove` (`local.py:135`) and
passes it to `delete_state` (`:137`). If the launch worktree was an **ephemeral
agent worktree** (`Agent(isolation: "worktree")`) that has since been reaped,
both operations fail: the cwd is gone and `git -C <gone> rev-parse` errors. The
isolation workspace must not depend on the (possibly transient) worktree it was
launched from.

## Design

### 1. `_git_common_dir(repo_root)` helper (types.py)

Resolve the **shared** git dir — a real directory for both main checkouts and
linked worktrees:

```python
def _git_common_dir(repo_root: Path) -> Path:
    """The shared .git directory, resolved for main checkouts AND linked
    worktrees. In a worktree <repo>/.git is a gitfile, not a dir; the common
    dir (<main>/.git) is the real directory all worktrees share — the correct
    place to key isolation state (state is repo+branch, not per-worktree)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Not a git repo (e.g. a bare tmp path in a unit test) — degrade to the
        # literal legacy behavior; there is no worktree to be blind to here.
        return repo_root / ".git"
    p = Path(out)
    return p if p.is_absolute() else (repo_root / p)
```

- For a **main checkout**, `--git-common-dir` returns `.git` (relative) →
  resolves to `repo_root / ".git"` — **byte-identical** to today. No behavior
  change on the normal path. (Existing `test_state_roundtrip` /
  `test_legacy_*` assertions of `startswith(repo / ".git")` stay green.)
- For a **linked worktree**, git returns the absolute `<main>/.git`.
- `check=True` with a graceful fallback keeps the helper *total* — a unit test
  that passes a non-repo path gets the old literal `.git`, not a new crash.

`types.py` already imports `os`/`sys`/`Path`; add `import subprocess`.

### 2. `state_dir` / `_legacy_state_dir` use the helper (types.py)

```python
def state_dir(repo_root: Path) -> Path:
    return _git_common_dir(repo_root) / "fr" / "isolation"

def _legacy_state_dir(repo_root: Path) -> Path:
    return _git_common_dir(repo_root) / "vk" / "isolation"
```

This transitively fixes `state_path`, `save_state`, `delete_state`,
`load_state`, and `list_states`. State location becomes **worktree-invariant**:
`state_path(main, b) == state_path(worktree_of_main, b)`.

### 3. `migrate.py` uses the helper

```python
common = _git_common_dir(repo_root)
vk_state = common / "vk" / "isolation"
fr_state = common / "fr" / "isolation"
```

(Import `_git_common_dir` from `fr.isolation.types`.) Migration run from a
worktree no longer crashes and writes to the shared location.

### 4. Normalize `repo_root` to the main toplevel (local.py)

In `LocalWorktreeDevcontainerTarget.__init__`, resolve the **main checkout's**
toplevel so the Target — and the state it persists — is independent of the
launch worktree:

```python
def __init__(self, repo_root: Path, runner: Runner = subprocess_runner):
    # Normalize to the MAIN worktree's toplevel: when launched from inside a
    # linked worktree (e.g. an ephemeral agent worktree), key everything off
    # the durable main checkout so state + the spawned worktree survive the
    # launch worktree being reaped. No-op for a main checkout. (#292)
    self.repo_root = _main_worktree_root(Path(repo_root).resolve())
    self.run = runner
```

```python
def _main_worktree_root(repo_root: Path) -> Path:
    common = _git_common_dir(repo_root)          # <main>/.git for any worktree
    return common.parent if common.name == ".git" else repo_root
```

`_main_worktree_root` lives in `local.py` (or is imported alongside
`_git_common_dir` from `types`). For a non-bare repo the common dir is always
`<toplevel>/.git`, so `.parent` is the main toplevel; the `common.name == ".git"`
guard falls back safely for anything unusual (and for the non-repo test path,
where `_git_common_dir` returned `repo_root / ".git"`, whose parent is
`repo_root` — also a safe no-op).

Consequences (all desirable):

- `state.repo_root` is now the main toplevel → `down`'s `git worktree remove`
  cwd and `delete_state` survive a reaped launch worktree.
- The worktree cache bucket (`local.py:64`, `self.repo_root.name`) is the real
  repo name, not the launch-worktree's mangled branch name.
- `git worktree add` (`_git_worktree_add`, cwd=`self.repo_root`) and `_pr`
  run from the main checkout — always valid.

### 5. `.git` bind-mount uses the common dir (local.py:72)

```python
git_dir = _git_common_dir(self.repo_root)
```

After step 4, `self.repo_root` is the main toplevel, so `self.repo_root/.git`
is already a real directory — this change is belt-and-suspenders, but it makes
the intent explicit and keeps the mount correct even if a caller bypasses
`__init__` normalization. The mount maps the host common-dir path to the same
in-container path (the existing scaffold comment at `scaffold.py:85-87` explains
why host-path-identical mounts are required for linked-worktree gitdir
back-pointers to resolve in-container).

`scaffold.py` itself needs **no change**: lines 85-87 are an explanatory
comment, and the config it writes uses `${localWorkspaceFolder}` /
`repo_root.name` — neither hardcodes a `.git` path.

## Non-goals

- **No change to `resolve_repo_root()` (global).** Normalization is confined to
  the isolation Target; other `fr` verbs keep `--show-toplevel` semantics.
- **No bare-repo support.** fr isolation already requires a normal checkout
  (`if not (self.repo_root / ".git").exists()` guard).
- **No change to on-disk state format** or to the legacy dual-read/warn paths
  beyond pointing them at the common dir.

## Tests (TDD)

All use the existing `make_repo` fixture (real throwaway git repos) and the
`FakeRunner` seam — no Docker.

1. **`state_dir` worktree-safe (RED first).** `make_repo` → `git worktree add`
   a linked worktree → call `save_state`/`state_path`/`load_state`/`delete_state`
   with the **worktree** path as `repo_root`. Assert: (a) no raise, (b) the file
   lands under `<main>/.git/fr/isolation`, (c) round-trips, (d)
   `state_path(main, b) == state_path(worktree, b)` (worktree-invariant key).

2. **legacy `_legacy_state_dir` worktree-safe.** Same shape, asserting the
   `vk/isolation` reads resolve under the common dir from a worktree.

3. **`up` from a worktree (local.py).** Construct
   `LocalWorktreeDevcontainerTarget(<worktree path>, FakeRunner)`; assert
   `target.repo_root` == main toplevel. Run `up()`; assert: (a) the
   `--mount=...source=<main>/.git...` arg targets the main `.git` (a real dir),
   (b) `state.repo_root` == main toplevel, (c) the spawned worktree path is
   under `~/.cache/fr/worktrees/<main-repo-name>/`.

4. **`migrate_repo` from a worktree** doesn't crash and computes the
   `.git/vk` → `.git/fr` move under the common dir.

5. **No-behavior-change regression (main path).** Existing
   `test_state_roundtrip` and legacy tests must stay green unmodified —
   `--git-common-dir` returns `.git` for a main checkout, so paths are identical.

## Release

Per `CLAUDE.md` release rule, this touches `src/**` → **patch** version bump
via `scripts/bump-version.py`. There is in-flight 3.1.5 work in a separate
workspace; resolve to the next free patch at delivery to avoid a collision
(bump as the final implementation step, then `--check`).

## Implementation Plans

| Plan | Repo | File | Depends on |
| ---- | ---- | ---- | ---------- |
| 2026-06-09-isolation-worktree-gitfile | `derio-net/super-fr` | `2026-06-09-isolation-worktree-gitfile` | — |
