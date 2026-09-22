# A pipeline sentinel has three states — decide them, don't count worktrees

- **Issues:** [#472](https://github.com/derio-net/super-fr/issues/472),
  [#529](https://github.com/derio-net/super-fr/issues/529),
  [#432](https://github.com/derio-net/super-fr/issues/432)
- **Date:** 2026-09-21
- **Status:** designed; revised after adversarial review (see plan journal `adv-*`)

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
`workspaces` list: every workspace of this repo the session has bound, each **relative
to the fr cache dir** (`~/.cache/fr`), e.g. `worktrees/super-fr/fix__x`. It is a
**set**, not one stamp: a session may bind more than one workspace
(`fr isolation exec --branch <other>` rebinds), and a single replaced stamp let the
other workspace's teardown disarm this session's live pipeline (review C1). Relative, never absolute, so the
stamp carries no home path (operator decision). The sentinel's `repo_root`, which the
hook has always written absolute, is unchanged.

- **Writer:** `fr.isolation.sessions.attach` — the single place a session is bound to a
  workspace (`fr isolation attach`, `up --session`, and the `fr-session-bind.sh` hook all
  route through it). After binding it adds the worktree to that session's sentinel if
  one exists, pruning entries whose directory is gone. It rewrites atomically and
  preserves every other key. The bind hook recognises env-prefixed and `uv run` forms
  through the same strip the guard uses (one helper in the hook library): without it,
  `FR_ISOLATION_TARGET=worktree fr isolation up`, the guard's own prescribed command,
  never bound (review H1).
- A worktree outside the cache dir (no relative form) is **not stamped**: the sentinel
  stays fresh, i.e. armed — the guard's fail-closed posture.
- **Only a worktree of the sentinel's own repo stamps it** (git common dirs compared;
  unreadable = foreign). A session holding a pipeline in repo A may enter repo B's
  isolation (#421); stamping B's worktree into A's sentinel would read as orphaned and
  silently retire A's live pipeline.
- **The stamp survives a pipeline-skill reload.** `fr-pipeline-sentinel.sh` runs on every
  fr-goal / fr-brainstorming / fr-execute load, and fr-goal loads fr-brainstorming *after*
  `fr run start` has bound. The writer therefore carries an existing `workspace` forward
  entries whose directory still exists, when the `repo_root` is unchanged. A dead
  stamp is the previous pipeline's and is dropped: carried forward, it would read as
  orphaned and retire the new pipeline on its first command. A carried *live* entry
  cannot disarm a new pipeline in the same session, because healing needs **every**
  entry gone and the new workspace joins the set when it binds. The writer never *adds*
  an entry; only `attach` does. The write is tmp + `mv`.
- A new helper `stamp_sentinel_workspace(session_id, worktree)` in
  `fr/isolation/types.py`, beside `clear_repo_sentinels`, owns the format.

### 2.B The guard decides the state from the sentinel alone

The count-based heal is **deleted**. In its place, per-sentinel:

1. no entries → **fresh**: never healed, whatever `git worktree list` says.
2. entries: **live** iff at least one resolves (`${HOME}/.cache/fr/<entry>`) to a
   directory that is a listed linked worktree of the repo; else **orphaned**.
   Orphaned → `rm` only this session's sentinel, allow the command.
3. A failed `git worktree list` (non-git cwd) → treated as live/unknown, deny
   (fail closed, as today).
4. **The pipeline repo is itself a workspace** — its own toplevel carries a marker that
   validates under the edit gate's predicate (external mode: a preparer's primary
   checkout plus container evidence) → allow, sentinel kept. Such a checkout has no
   linked worktree and nothing to stamp; the count heal used to clear its sentinel by
   accident, and without this it would be denied every command. A `worktree`-mode marker
   cannot validate in a primary checkout, so a host base clone is never opened by it.

A relative `cd <target>` is anchored to the session's cwd where the target is parsed,
not to the hook process's cwd, so every later use of it judges the same directory.

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

### 2.C′ `fr isolation down` clears only its own workspace's sentinels

`down` (single) retires, after a **successful** teardown, the sentinels listing the
torn-down worktree or belonging to sessions bound to it (`clear_workspace_sentinels`).
A sentinel that still lists another live workspace only loses the entry. The guard no
longer retires anything on `fr isolation down`: it runs *before* the command, so it
ended pipelines for a `down` that then refused (open PR, dirty worktree), for
`--branch <another session's>`, and for `--help` (review H2). The previous rule, "zero
workspaces remain → clear every sentinel for the repo", is removed: it also retired
another session's *fresh* sentinel — a pipeline whose workspace did not exist yet —
which is #472's third mechanism. `down --all` keeps its repo-wide clear on purpose: it
is the explicit, now explicitly-warned, last resort.

### 2.D verify-merge after gc

`fr isolation verify-merge --branch <b>`, when no workspace state exists for the branch,
no longer errors: it fetches `origin/<default>` and `origin/<b>` (a failed fetch of the
branch is not a verdict — GitHub deletes merged branches), then requires the changes of
EVERY surviving ref — `origin/<b>` and the local branch gc keeps — to be on the base (a
post-merge push from another clone lives only on the first, an unpushed commit only on
the second; review M1), runs the same content check from the repo root, consults the PR state,
and prints that the workspace was already reaped. `verified` still requires all three
signals. An unresolvable branch ref exits **2** (usage) with a message naming the ref,
never 1: fr-goal reads 1 as "not verified, recover", and a typo disproves nothing.
No `--branch` given and no workspace remains keeps the existing error.

### 2.F Known limits, stated

- The sentinel writer and `attach` both read-modify-rename the same file; a skill load
  running concurrently with a bind could drop an entry (fresh, i.e. armed). Needs
  parallel tool calls; not fixed.
- The 48h GC keys on mtime and nothing refreshes a live sentinel, so a pipeline longer
  than 48h is disarmed by the next skill load. Pre-existing, unchanged.

## 3. Non-goals

- `down --all` behaviour (#533); the OpenCode/Hermes guards (they have no sentinel
  heal); the stale published explainer (#535 — no committed source).

## 4. Test Plan

Unit: guard hook tests (fresh never healed even with zero worktrees; orphaned healed
with other sessions' worktrees present, only this sentinel removed; live stays denied;
legacy unstamped stays armed; non-git fails closed; cd-target-gone message; standard
message no longer says `down --all` without warning), `attach` stamping (relative path,
preserves keys, restamp, outside-cache not stamped, no sentinel = no-op), verify-merge
fallback (reaped workspace verified / not verified / unresolvable ref exits 2), `down`
sparing a stranger's fresh sentinel, the self-isolated (external) repo allowed, relative
`cd` anchored to the session cwd, and — end to end over the REAL hooks
(`tests/unit/test_sentinel_lifecycle.py`) — the stamp surviving fr-goal's
fr-brainstorming reload, a foreign-repo bind never disarming the pipeline, and a dead
stamp never carrying into a new pipeline.
Post-merge — operator-driven: none required (no deployed surface).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-21-sentinel-three-states | `derio-net/super-fr` | `2026-09-21-sentinel-three-states` | — |
