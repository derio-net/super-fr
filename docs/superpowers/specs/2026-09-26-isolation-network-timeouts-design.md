# isolation: bound the default-branch lookup and verify-merge's fetch

- **Date:** 2026-09-26
- **Status:** designed
- **Origin:** super-fr#618 (batch `isolation-timeouts`, triage-batches phase 4 live walk)
- **Journal:** `docs/superpowers/journals/specs/2026-09-26-isolation-network-timeouts.md`
- **Goal:** no network-touching call on the isolation lifecycle's `verify-merge`, `up` and `gc` paths can hang the command: each is bounded and non-interactive, and a timeout reads as "unknown", never as a verdict.

## 1. Problem

`isolation/local.py` already has `_run_network` (a 60 s timeout, stdin from
`/dev/null`, `GIT_TERMINAL_PROMPT=0`, ssh in `BatchMode`), added for the
remote-branch probe (#438). Two families of call still bypass it and go through
the bare `self.run`, which has no timeout:

1. **`_resolve_default_branch`** falls from `git symbolic-ref
   refs/remotes/origin/HEAD` to a forge CLI — `gh repo view`, `glab repo view`
   or `tea repos` — when `origin/HEAD` is not set. A forge CLI that hangs (an
   expired token prompting for a login, a stalled network) hangs everything that
   resolves the default branch: `up`, `gc` and a bare `verify-merge`.
2. **`verify_merge`'s fetches.** `_verdict` runs `git fetch <remote>
   <default_branch>` and `_branch_refs` (the reaped path) runs `git fetch
   <remote> <branch>`, both untimed. A hung fetch hangs `verify-merge`, the
   post-merge close-out's first command.

The issue asks for the first; the batch note extends it to the second.

## 2. Decisions

| # | Decision |
|---|---|
| d1 | The three forge-CLI branches of `_resolve_default_branch` call `_run_network`, not `self.run`. Their `cwd` is already `repo_root`, which `_run_network` uses. |
| d2 | `_verdict`'s and `_branch_refs`'s fetches call `_run_network`. `_run_network` gains an optional `cwd` (default `repo_root`), because `_verdict` fetches from the workspace's worktree for a live branch. |
| d3 | A timeout needs no new handling. `run` already returns exit 124 with a `timed out after Ns` stderr; `_resolve_default_branch` already treats any non-zero exit as "fall through to `main`", and `_verdict` already reads a failed fetch as `fetched: false`, hence `verified: false` (#354: unknown is never a pass). |
| d4 | No new timeout constant. The forge lookup shares `_NETWORK_TIMEOUT_S`. |
| d5 | The fetch in `_reap_hazard` (`gc`'s unlanded-content check, `local.py` around l.1164) has the same defect but is not in the batch note; it is filed out of scope, not fixed here. |

## 3. Design

### 3.A `_run_network(argv, cwd=None)`

`cwd` defaults to `self.repo_root`, so every existing caller is unchanged.

### 3.B `_resolve_default_branch`

Replace the three `self.run(...)` forge calls with `self._run_network(...)`.
Nothing else changes: the `symbolic-ref` step stays on `self.run` (local, no
network), and a timed-out lookup returns `main`, exactly as any failed lookup
does today.

`_network_env` sets git variables only (`GIT_TERMINAL_PROMPT`,
`GIT_SSH_COMMAND`), which `gh`/`glab`/`tea` ignore; what protects the forge CLIs
is the timeout and stdin from `/dev/null`, which `run` applies whenever a
timeout is given. `_network_env` also issues one local, cheap `git config --get
core.sshCommand` before the real call (skipped when `GIT_SSH_COMMAND` or
`GIT_SSH` is set). That extra call now precedes the forge lookups and the
verify-merge fetches too; it is accepted rather than special-cased, and tests
that script the runner must select calls by argv, not by position or count.

### 3.C `verify-merge`

`_verdict` calls `self._run_network(["git", "fetch", remote, default_branch],
cwd=cwd)`; `_branch_refs` calls `self._run_network(["git", "fetch", remote,
branch])`. Only the `_verdict` fetch feeds `fetched` (and so `verified`); the
`_branch_refs` fetch's result is discarded today, and stays so: when it times
out, the reaped path falls back to whatever refs the clone still has, or raises
`IsolationError` when none resolves.

## 4. Obligations

- **Acceptance matrix:** this spec's Test Plan is cited by the new row
  `isolation-network-calls-bounded` (added at brainstorm as `not-implemented`),
  which the implementing phase moves to `ci` with `fr acceptance set-status`.
- **Version:** patch bump to `4.23.2` (reserved for this batch) via
  `scripts/bump-version.py`, since `packages/fr/src/**` changes.

## 5. Non-goals

- The `_reap_hazard` fetch (d5).
- Changing the timeout value, or making it configurable.
- Caching the resolved default branch.

## 6. Test Plan

Post-merge — operator-driven: none; the behaviour is unit-pinned per PR.

1. **Forge lookup is bounded.** With `origin/HEAD` unset, a runner double records
   the call: the `gh`, `glab` and `tea` lookups each carry a non-`None` timeout
   and the workspace's repo root as `cwd`. A lookup that returns exit 124 yields
   `main`.
2. **verify-merge fetches are bounded.** `verify_merge` and
   `verify_merge_reaped` issue both their fetches with a timeout. A default-branch
   fetch (`_verdict`) that times out gives `fetched: false` and `verified: false`
   even when content and PR state say merged. A branch fetch (`_branch_refs`)
   that times out changes no verdict: the local refs are used, or `IsolationError`
   is raised when none resolves.
3. **Local steps stay unbounded.** The `symbolic-ref` call is not given a
   timeout (asserted by argv, not by call count), and `_run_network`'s existing callers behave as before.
