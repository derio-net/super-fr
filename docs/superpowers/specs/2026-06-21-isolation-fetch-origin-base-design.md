# Isolation cold-start: fetch + base new branches on `origin/<default>`

**Issue:** [#322](https://github.com/derio-net/super-fr/issues/322)
**Status:** design
**Date:** 2026-06-21

## Problem

`fr isolation up` creates a new worktree branch from the base repo's **current
HEAD**, with no `git fetch` and no canonical base ref. If the base repo is
parked on a feature branch (or a stale local `main`), the new isolated branch
silently inherits that branch's un-merged commits — and they ride into the
resulting PR.

`fr/isolation/local.py::_git_worktree_add` (packages/fr/src/fr/isolation/local.py:181):

```python
def _git_worktree_add(self, worktree, branch):
    if worktree.exists():
        return                                               # (1) reuse: idempotent
    branches = self.run(["git", "branch", "--list", branch], cwd=self.repo_root)
    if branches.stdout.strip():
        argv = ["git", "worktree", "add", str(worktree), branch]       # (2) reuse: existing branch
    else:
        argv = ["git", "worktree", "add", str(worktree), "-b", branch] # (3) NEW branch, NO start-point ← BUG
    ...
```

Path (3) — a genuinely **new** branch — resolves to the current HEAD of
`cwd=self.repo_root`. There is no `git fetch` and no `origin/...` reference
anywhere in `up()` or `isolation_cmd.py`.

**Real incident:** `fr-debugging` cold-start while the base repo was parked on
`fix/frank-routes-selfauth-no-forwardauth` (HEAD = an un-merged commit). The new
isolation branch forked from that HEAD, so the fix PR (frank#594) inherited an
unrelated `ingressroutes.yaml` change. Required a manual
`git rebase --onto origin/main <stray> <branch>` + force-push to clean up.

## Key structural insight

`_git_worktree_add` already distinguishes **reuse** from **cold-start** by
construction:

- Path (1) existing worktree → return early (continuation of the same workspace).
- Path (2) existing branch → check it out as-is (continuation / reuse).
- Path (3) neither → create a brand-new branch. **This is the only cold-start path.**

So the fix targets path (3) **only**. Reuse and continuation flows are never
rebased onto `origin/main` — issue corner case #1 ("continuation/reuse must NOT
rebase onto main") is satisfied without adding any new reuse-vs-cold-start
branch logic. The CLI already distinguishes the two; we only change what
start-point the new-branch case uses.

## Operator decisions (batched Q&A, 2026-06-21)

1. **Default base for a new cold-start branch:** `git fetch origin`, then base
   the new branch on `origin/<default-branch>`. (Not "keep current HEAD".)
2. **Default-branch resolution:** `git symbolic-ref refs/remotes/origin/HEAD`
   (refreshed via `git remote set-head origin --auto` after the fetch) →
   fall back to `gh repo view --json defaultBranchRef` → final fallback `main`.
3. **Override surface:** both `--base <ref>` and `--no-fetch` flags, **plus**
   an automatic fallback to local HEAD (with a `WARNING` log line) when there
   is no `origin` remote or the fetch fails — never error out.

## Design

### Behavior matrix (new-branch path only; reuse paths unchanged)

| Invocation | fetch? | start-point for `-b <branch>` |
|---|---|---|
| `up --branch feat/x` (default) | yes (`origin`) | `origin/<default>` (resolved) |
| `up --branch feat/x --base HEAD` | no | `HEAD` (intentional stacking / current-base) |
| `up --branch feat/x --base <ref>` | no | `<ref>` verbatim (explicit, e.g. a tag or sha) |
| `up --branch feat/x --no-fetch` | no | `origin/<default>` from **local** remote-tracking ref |
| default, but no `origin` remote | n/a | local `HEAD` + WARNING (auto-fallback) |
| default, but `git fetch origin` fails (offline) | attempted | local `HEAD` + WARNING (auto-fallback) |

Rules:

- **`--base <ref>` given** → the operator named an explicit start-point; do
  **not** fetch and do **not** resolve the default branch. Use `<ref>` as-is.
  `--base HEAD` is the documented way to opt back into the old "fork from
  current checkout" behavior (stacking, intentional current-branch debugging).
- **`--no-fetch` given (no `--base`)** → skip the network fetch but still base
  on `origin/<default>` using whatever local remote-tracking ref exists. If that
  ref is missing, auto-fallback to local HEAD + WARNING.
- **Neither flag (default)** → `git fetch origin`, resolve `<default>`, base on
  `origin/<default>`.
- **`--base` and `--no-fetch` together** → `--base` wins (already no fetch);
  `--no-fetch` is redundant, not an error.
- **Auto-fallback** (no remote, or fetch fails, or remote-tracking ref absent)
  → base on local `HEAD`, emit a single `WARNING` line naming the base actually
  used. The run never aborts on a base-resolution problem.

### Default-branch resolution (`_resolve_default_branch`)

Used only when basing on `origin/<default>` (default path, or `--no-fetch`
without `--base`). Order:

1. After a successful `git fetch origin`, run `git remote set-head origin --auto`
   (cheap, no extra network — uses the just-fetched refs) to (re)point
   `refs/remotes/origin/HEAD`. On `--no-fetch`, skip this step.
2. `git symbolic-ref --short refs/remotes/origin/HEAD` → strip the `origin/`
   prefix → that is `<default>`.
3. If symbolic-ref is unset/fails, `gh repo view --json defaultBranchRef
   --jq .defaultBranchRef.name` (only if `gh` resolves; tolerate non-zero/empty).
4. Final fallback: `main`.

The resolved `origin/<default>` ref must exist locally before use (it does,
after a successful fetch). If it does not (e.g. `--no-fetch` and never fetched),
auto-fallback to local HEAD + WARNING.

### Logging

`up()` emits one informational line stating the base actually used, e.g.:

- `isolation: basing new branch feat/x on origin/main (fetched)`
- `isolation: basing new branch feat/x on origin/main (local, --no-fetch)`
- `isolation: basing new branch feat/x on HEAD (--base)`
- `WARNING: no origin remote — basing feat/x on local HEAD` (auto-fallback)
- `WARNING: git fetch origin failed (<short reason>) — basing feat/x on local HEAD`

These print on the host side (the CLI), consistent with the existing
`isolation up: ...` summary line.

## Implementation surface

### `packages/fr/src/fr/isolation/local.py`

- `up(self, profile, branch, path=None, base=None, no_fetch=False)` — thread the
  two new params through to `_git_worktree_add`.
- `_git_worktree_add(self, worktree, branch, base=None, no_fetch=False)` — paths
  (1) and (2) unchanged; path (3) computes the start-point per the matrix above
  and appends it to the `git worktree add ... -b <branch> <start-point>` argv.
- New helpers (small, Runner-seam-routed so they stay unit-testable):
  - `_has_origin_remote()` → `git remote` lists `origin`.
  - `_fetch_origin()` → `git fetch origin`; returns success bool (never raises).
  - `_resolve_default_branch()` → the symbolic-ref → gh → `main` chain.
  - `_cold_start_base(branch, base, no_fetch)` → returns
    `(start_point: str | None, log_line: str)`; encapsulates the whole matrix.
    `start_point` is the ref string to append after `-b <branch>`, or `None`
    meaning "append no start-point" — i.e. let git default to current HEAD.
    `None` is returned for `--base HEAD` and for every auto-fallback case.

  So "base on local HEAD" is expressed by passing **no** start-point to
  `git worktree add -b` (git's default = current HEAD), byte-identical to
  today's command — the auto-fallback path is therefore a no-op regression
  against current behavior.

All new external calls go through `self.run` (the Runner seam) so tests fake
them without Docker/network. Git calls that must hit a real repo (fetch,
symbolic-ref, worktree add) run against a **real bare `origin` remote** in tests
(see Testing).

### `packages/fr/src/fr/commands/isolation_cmd.py`

Add to the `up` command:

```python
base: str | None = typer.Option(
    None, "--base", help="Start-point for a NEW branch (e.g. origin/main, HEAD, <sha>). "
                         "Given → no fetch, no default-branch resolution."),
no_fetch: bool = typer.Option(
    False, "--no-fetch", help="Skip git fetch; base a new branch on the local "
                              "origin/<default> tracking ref (or HEAD if absent)."),
```

Pass both through to `_target(repo).up(...)`. The `Target` Protocol in
`types.py` gains the two optional params on `up` (defaulted, so the remote
target stub stays compatible).

### Skill docs (user-observable behavior → version bump)

Update the three skills that drive `fr isolation up` so operators learn the new
default and the escape hatches:

- `plugins/super-fr/skills/fr-isolation/SKILL.md` — document the cold-start
  default (fetch + origin/<default>) and `--base` / `--no-fetch`.
- `plugins/super-fr/skills/fr-debugging/SKILL.md` — the cold-start block: note
  that a standalone fix now cuts from freshly-fetched `origin/<default>`; if a
  bug is genuinely meant to be debugged on the current branch, use `--base HEAD`.
  Reuse path wording is unchanged (it never rebases).
- `plugins/super-fr/skills/fr-brainstorming/SKILL.md` — the `fr isolation up`
  invocation line gains a one-line note that new branches base on
  `origin/<default>` by default.

(fr-goal's SKILL.md is at its 120-line budget; only touch it if a line genuinely
must change — the new default is transparent to fr-goal's flow, so prefer not to.)

### Version bump

Touches `packages/fr/src/**` and `plugins/*/skills/**` → bump required.
`scripts/bump-version.py patch` (3.4.1 → 3.4.2). Per CLAUDE.md this is a patch
(CLI fix + skill copy), not a minor — the default change is a bugfix to match
documented operator expectation, not a new user-visible workflow.

## Testing

Unit tests in `tests/unit/test_isolation.py` and `tests/unit/test_isolation_cmd.py`,
using the existing `make_repo` + `FakeRunner` seam. `FakeRunner` delegates git
to the real binary, so:

- Extend a `make_repo`-style helper to create a **real bare `origin`** (`git init
  --bare`), `git remote add origin`, push `main` — so `git fetch origin`,
  `git remote set-head origin --auto`, and `origin/main` resolution all run for
  real and are asserted via merge-base.

Cases:

1. **Default cold-start bases on origin/<default>, not local HEAD.** Park the
   base repo on a feature branch with an un-merged commit; `up --branch feat/x`;
   assert `git merge-base feat/x origin/main == origin/main` and the stray commit
   is **not** reachable from `feat/x`. (Direct regression for the incident.)
2. **`--base HEAD` forks from current checkout** (stacking) and does **not**
   fetch (assert no `git fetch` ran / current-HEAD parent).
3. **`--base <ref>` uses the explicit ref** verbatim, no fetch.
4. **`--no-fetch` bases on the local origin/<default> tracking ref** without a
   fetch call; if the tracking ref is absent → auto-fallback to HEAD + WARNING.
5. **No `origin` remote → auto-fallback to local HEAD + WARNING**, exit 0.
6. **Fetch fails (simulated) → auto-fallback to local HEAD + WARNING**, exit 0.
7. **Default-branch resolution:** symbolic-ref present wins; absent → gh path;
   gh absent/empty → `main` fallback. (Drive via FakeRunner stdout for `gh`;
   symbolic-ref against the real bare-origin repo.)
8. **Reuse paths untouched:** existing-worktree (idempotent) and existing-branch
   checkout neither fetch nor change start-point (regression guard for corner
   case #1).
9. **CLI plumbing:** `isolation_cmd.up` forwards `--base` / `--no-fetch` to
   `Target.up` (monkeypatched target, assert kwargs).

CI gate (per CLAUDE.md): `uv run ruff format packages/ tests/`,
`ruff check`, `mypy packages/fr/src ...`, `uv run pytest -q --no-cov`,
`bump-version.py --check`.

## Out of scope / YAGNI

- Per-repo config key for the base branch/policy (the Q&A chose flags +
  auto-fallback, not a config knob).
- Rebasing or updating the **local** `main` ref — we base on the remote-tracking
  `origin/<default>` directly, so the local branch is never touched.
- Changing reuse/continuation semantics in any way.
- A `--base` that also triggers a fetch — explicit `--base` means "I named the
  ref, use it"; fetching is the default path's job.
