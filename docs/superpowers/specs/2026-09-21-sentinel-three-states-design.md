# A pipeline sentinel has three states — decide them, don't count worktrees

- **Issues:** [#472](https://github.com/derio-net/super-fr/issues/472),
  [#529](https://github.com/derio-net/super-fr/issues/529),
  [#432](https://github.com/derio-net/super-fr/issues/432)
- **Date:** 2026-09-21
- **Status:** designed

## 1. Problem

`plugins/super-fr/hooks/fr-isolation-guard.sh` self-heals ("the sentinel has OUTLIVED all
worktrees") by counting `worktree ` lines in `git worktree list` and clearing the
sentinel when there is exactly one. That count is a repo-wide proxy for a per-session
fact, and it fails in both directions:

- **#472 — never heals.** Any *other* session's worktree (or a Claude subagent
  checkout) keeps the count above one, so a session whose own workspace was gc-reaped is
  locked out of every base-clone command.
- **#529 — heals too eagerly.** A *fresh* pipeline has not created its worktree yet, so
  the count is also one; the first base-clone command (`ls` included) deletes the
  sentinel and silently disarms the guard for the whole session.

#529 constrains #472: widening the predicate makes #529 worse, narrowing it hardens
#472. The two cannot both be fixed by any count, because the code has **two** states
where a sentinel legally has **three**:

| state | meaning | guard behaviour |
|---|---|---|
| **fresh** | pipeline started, no workspace ever bound | armed; deny, say "enter isolation" |
| **live** | a workspace was bound and still exists | armed; deny, say "cd into it" |
| **orphaned** | a workspace was bound and is gone | retire THIS sentinel, allow |

"Never had one" versus "had one, lost it" is a **recorded fact**, not something
inferable from `git worktree list`.

#432 is the same code path's denial text: it advertises `fr isolation down --all`
unconditionally to a session that cannot see other sessions' workspaces (`--all` tears
down pre-PR workspaces, uncommitted work included), and there is no branch that says a
`cd` target no longer exists when a reaped worktree is what made the prescribed escape
unsatisfiable. Related report in #432: `fr isolation verify-merge --branch <b>` errors
after gc reaps the workspace — fr-goal's post-merge close-out prescribes it first.

## 2. Design

### 2.A The sentinel records its workspace

The sentinel (`~/.cache/fr/sentinels/<session>.json`) gains an optional
`workspace` field: the bound worktree path **relative to the fr cache dir**
(`~/.cache/fr`), e.g. `worktrees/super-fr/fix__x`. Relative, never absolute, so the
username never lands in the file (operator decision).

- **Writer:** `fr.isolation.sessions.attach` — the single place a session is bound to a
  workspace (`fr isolation attach`, `up --session`, and the `fr-session-bind.sh` hook all
  route through it). After binding it stamps `workspace` into that session's sentinel if
  one exists. It rewrites atomically and preserves every other key. A re-`attach` to a
  different workspace restamps (a session holds at most one binding).
- A worktree outside the cache dir (no relative form) is **not stamped**: the sentinel
  stays fresh, i.e. armed — the guard's fail-closed posture.
- A new helper `stamp_sentinel_workspace(session_id, worktree)` in
  `fr/isolation/types.py`, beside `clear_repo_sentinels`, owns the format.

### 2.B The guard decides the state from the sentinel alone

The count-based heal is **deleted**. In its place, per-sentinel:

1. no `workspace` key → **fresh**: never healed, whatever `git worktree list` says.
2. `workspace` set: resolve `${HOME}/.cache/fr/<workspace>`; it is **live** iff the
   directory exists **and** is a listed linked worktree of the repo; else **orphaned**.
   Orphaned → `rm` only this session's sentinel, allow the command.
3. A failed `git worktree list` (non-git cwd) → treated as live/unknown, deny
   (fail closed, as today).

Consequences: #529 — a fresh sentinel is never healed. #472 — an orphaned sentinel
heals regardless of other sessions' worktrees, and only this session's sentinel is
removed. Legacy unstamped sentinels read as fresh and stay armed until `fr isolation
down` or the existing 48h GC — deliberately fail-closed; the drawback (a pre-upgrade
orphan is not healed) is bounded by that GC and stated in the rule text.

A sentinel that is never stamped (no session id from the harness) stays armed until
48h GC or `down` — operator decision; no grace-window timeout.

### 2.C Denial messages (#432), guard-side only

- **cd target gone:** when the command leads with `cd <path>` and `<path>` does not
  exist, say so: it no longer exists — an fr worktree is removed once its branch merges;
  start one with `fr isolation up --branch <name>` or `cd` into a live one (`fr isolation
  status`).
- **Stop advertising `down --all` unconditionally.** The standard denial points at
  `fr isolation status` and `fr isolation up --branch <name>` first. `down --all` remains
  only as an explicitly-warned last resort ("acts on every workspace in this repo,
  including other sessions' — a workspace with no PR yet is torn down").
- Hardening `down --all` itself (blast-radius listing, pre-PR shield) is out of scope;
  filed as a follow-up.

### 2.D verify-merge after gc

`fr isolation verify-merge --branch <b>`, when no workspace state exists for the branch,
no longer errors: it fetches `origin/<default>`, resolves the branch ref (local, else
`origin/<b>`), runs the same content check from the repo root, consults the PR state,
and prints that the workspace was already reaped. `verified` still requires all three
signals; an unresolvable branch ref is **not verified** with a message naming the ref.
No `--branch` given and no workspace remains keeps the existing error.

## 3. Non-goals

- `down --all` behaviour; the OpenCode/Hermes guards (they have no sentinel heal); the
  sentinel writer `fr-pipeline-sentinel.sh` (a fresh sentinel is exactly its existing
  output — the absence of `workspace` *is* the fresh state).

## 4. Test Plan

Unit: guard hook tests (fresh never healed even with zero worktrees; orphaned healed
with other sessions' worktrees present, only this sentinel removed; live stays denied;
legacy unstamped stays armed; non-git fails closed; cd-target-gone message; standard
message no longer says `down --all` without warning), `attach` stamping (relative path,
preserves keys, restamp, outside-cache not stamped, no sentinel = no-op), verify-merge
fallback (reaped workspace verified / not verified / unresolvable ref).
Post-merge — operator-driven: none required (no deployed surface).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-21-sentinel-three-states | `derio-net/super-fr` | `2026-09-21-sentinel-three-states` | — |
