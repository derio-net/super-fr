# fr isolation: separate the container lifecycle from the worktree lifecycle

- **Date:** 2026-09-23
- **Status:** designed
- **Origin:** gh#577, gh#575, gh#471, gh#438
- **Goal:** each fr isolation verb touches exactly one of the two lifecycles (the
  container or the worktree), and none silently destroys or mis-seeds fr's own run
  record.

## 1. Problem

A workspace has two lifecycles: a **worktree** (branch, files, the uncommitted run
cursor, the `.fr-isolation` marker, session bindings) and a **container** (image,
features, running processes). Today fr's verbs bundle them:

| Need | Today | Consequence |
|---|---|---|
| Apply a changed profile (#577) | `restart` is `docker restart` (`local.py:430`); `up` on an existing workspace calls `devcontainer up` without `--remove-existing-container` (`local.py:392`) | The only way to recreate the container is `down --force && up`, which also deletes the worktree |
| Keep the run while repairing (#575) | `down --force` bypasses `_reap_hazard` for every dirty path alike | The uncommitted cursor at `<worktree>/docs/superpowers/runs/<id>.yaml` is deleted. Afterwards every `fr run` command prints `no run state at <path>`, which reads like a typo in the run id |
| Pause an idle container (#471) | No verb; `exec` calls `devcontainer exec` with no start step | Operators run `docker stop` by hand, then `exec` fails with a raw devcontainer error |
| Resume a remote-only branch (#438) | `_git_worktree_add` checks `git branch --list <B>` (local only) | `origin/<B>` is ignored, and a same-named branch is cut from `origin/main`. The worktree silently lacks the branch's commits |

The first two combine into the incident in #575: a broken container, repaired the
only documented way, cost a live `/fr-goal` run its cursor and the pipeline.

## 2. Goal

- **Container verbs** (`stop`, `restart`, `rebuild`, and the auto-resume in `exec`)
  never touch the worktree, branch, marker, bindings or run cursor.
- **Worktree verbs** (`down`, `gc`) name what they would destroy, and preserve fr's
  own uncommitted run record even when forced. The next `up` for that branch
  restores it.
- **`up`** seeds a worktree from the branch that already exists, local or remote,
  and names the tip it used.

Non-goals: `gc --stop-idle` (idle detection is deferred, per the operator), listing
containers across repos (the #471 comment), and any change to the edit gate or the
bash guard.

## 3. Design

### A. `fr isolation rebuild` (#577)

`fr isolation rebuild [--branch <b>] [--no-cache]` recreates the container against
the existing worktree and config:

```
devcontainer up --workspace-folder=<wt> --config=<cfg> --mount=<git common dir>
                --remove-existing-container [--build-no-cache]
```

- The argv is shared with `up` through one helper, `_devcontainer_up(state,
  remove_existing, no_cache)`, so the mount and config rules cannot drift between
  the two.
- `_ensure_mounted_env_file` runs first, as it does in `up`.
- It refuses when the worktree directory is gone ("run `fr isolation up`").
- It reports `isolation rebuild: <b> recreated (<old-id> → <new-id>); worktree
  untouched`. The new container id comes from a fresh `docker ps` query.
- The state record keeps its `created_at`, and the worktree, marker, bindings and
  cursor are never touched.
- The superseded `vsc-*` image is left to `gc`'s dangling-image sweep. It is not
  removed inline, because a rebuild that failed halfway must still have an image to
  fall back on.
- Host-worktree mode prints `nothing to rebuild — host-worktree mode has no
  container` and exits 0. External mode refuses (`environment is externally
  managed`), like `restart`.

`restart` keeps its meaning (process bounce, installs kept). Its help text now says
that it does NOT apply profile changes, and that it resumes a stopped container.

### B. `fr isolation stop` and a stopped-aware `exec` (#471)

- `fr isolation stop [--branch <b>]` runs `docker stop <id>` and verifies the
  container is no longer running with a follow-up `docker ps`.
  - The worktree, state, marker and bindings are kept.
  - An already-stopped container is a no-op success, and it says so.
  - With no container at all, it errors with the `up` hint.
  - Host-worktree mode is a no-op message; external mode refuses.
- `status` reports docker's `exited` state as `container=stopped`, in both text
  and JSON. `running`, `created` and other states pass through unchanged.
- `exec` checks the container state before running (`_ensure_running`):
  - **running**: exec as today.
  - **stopped, created or absent**: print `isolation: container for <b> was
    <state> — resuming (devcontainer up)` to stderr, run `_devcontainer_up(state,
    remove_existing=False)`, then exec. `devcontainer up` is the documented resume
    path. It also re-runs `postStartCommand`, which a bare `docker start` would
    skip.
  - **`docker ps` fails** (daemon unreachable): exit 2 with `docker is unreachable
    — cannot resume <b>`, never the raw devcontainer error.
  - **resume fails**: exit 2 naming the fix (`fr isolation rebuild --branch <b>`).
- The CLI's `exec` now catches `IsolationError` (it caught none before), so every
  failure prints fr's one-line message.
- `up` and `restart` help text states that both resume a stopped container.

### C. Preserve the run record across worktree teardown (#575)

A new module, `fr/isolation/preserve.py`, owns one directory per branch:

```
~/.cache/fr/runs/<repo-cache-name>/<branch-slug>/
  teardown.json   # {branch, worktree, torn_down_at, forced, head,
                  #  runs: [{id, cursor, finished, preserved}], files: [...]}
  files/<repo-relative path>   # copies of the preserved files
```

The key is `repo_cache_name` of the main checkout, the same key the worktree
cache uses, so a lookup from the base clone or from any sibling worktree finds it.

1. **Name the run in the hazard.** `_reap_hazard` reads every
   `docs/superpowers/runs/*.yaml` in the worktree.
   - A run is **active** when at least one of its step records is not `done`.
   - If the dirty-worktree check fires and an active run is present, the hazard
     becomes `kind="active-run"`. Its headline is `holds run <id> at step
     <cursor>`, followed by the dirty paths. The remedy text says what `--force`
     does now: the environment is removed, and the cursor is preserved and
     restored by `fr isolation up --branch <b>`.
   - `down_refusal` and the `down --all` preview use the same hazard, so all three
     name the run.
2. **Preserve before destroying.** `_down_worktree_tail` calls
   `preserve.snapshot(state)` after the guards and before
   `_teardown_container`. That covers `down`, `down --force`, `down --all` and
   `gc` reaps, because all of them go through that tail.
   - The snapshot copies every dirty or untracked path under `docs/superpowers/`
     (from `git status --porcelain -uall`): run cursors, journals, and spec or
     plan drafts. Together these are fr's own record.
   - It writes a tombstone entry for every run file in the worktree, clean or
     dirty.
   - When there is nothing to record, it writes nothing.
   - A snapshot that cannot be written raises `IsolationError`, and the down
     aborts with the workspace intact. `--force` buys the teardown of the
     environment, never a silent loss of the record.
   - A second teardown of the same branch merges into the existing directory.
     Newer copies win, and the tombstone keeps the union of runs.
3. **Say it at down time.** `down` returns a `TeardownReport`, and the CLI prints
   one line per active run it ended:
   `down: ended run <id> at step <cursor> in this workspace — cursor preserved at
   <dir>; \`fr isolation up --branch <b>\` restores it`.
4. **Restore on the next `up`.**
   - When `_git_worktree_add` creates a worktree (never when it reuses one), it
     calls `preserve.restore(repo_root, branch, worktree)`.
   - Each preserved file is copied back only if it is absent. An existing file is
     never overwritten; a conflicting copy is reported by path and left in the
     cache.
   - The tombstone is stamped with `restored_at`.
   - `up` prints `isolation: restored N preserved file(s) (run <id> at <cursor>)`.
   - Because `fr run start` reaches `up` through `ensure_run_workspace`, it
     restores too.
5. **An honest not-found.** `load_run_state` still raises `RunStateError` for a
   missing file. The message now comes from `preserve.explain_missing(repo_root,
   run_id, path)`:
   - **tombstone with a preserved cursor**: `run <id> is not in this checkout: its
     workspace for branch <b> (<worktree>) was torn down at <T>, and its cursor
     was preserved. \`fr isolation up --branch <b>\` restores it; run fr from
     there.`
   - **tombstone, cursor committed on the branch**: the same, ending `its cursor is
     committed on <b>. \`fr isolation up --branch <b>\`; run fr from there.`
   - **a live workspace of this repo holds it**: `run <id> lives in the workspace
     at <worktree> — run fr from there.`
   - **nothing**: `no run <id> at <path>, and fr has no record of one (never
     started here, or the id is mistyped) — \`fr run status\` lists this
     checkout's runs.`

   `fr journal` paths that load a run surface the same message, because they call
   the same loader.

### D. `up --branch` reuses `origin/<B>` (#438)

`_git_worktree_add` classifies the branch after a fetch, in this order:

| local `<B>` | `origin/<B>` | `--base` | Action | Log line |
|---|---|---|---|---|
| yes | no / same tip | any | reuse local, as today | `isolation: reusing local branch <B> at <sha>` |
| yes | diverged | any | reuse local | WARNING: `local <B> (<sha>) and origin/<B> (<sha>) have diverged — using local` |
| no | yes | none | `git worktree add --track -b <B> <wt> origin/<B>` | `isolation: reusing remote branch <B> at origin/<B> (<sha>)` |
| no | yes | given | **refuse** (exit 2) | `origin/<B> exists — --base would fork a second history under the same name; drop --base to reuse it, or pick another branch name` |
| no | no | any | cold start, as today (#322) | the existing `basing new branch …` line, with `(<sha>)` added |

- **Fetching.** Remote classification runs `git fetch origin <B>`, a targeted
  fetch that is cheap and never errors on a missing ref (its failure is read as
  "absent").
- **`--no-fetch` and no origin.** These keep today's behaviour, except that
  `--no-fetch` still consults an already-present local `origin/<B>` ref.
- **Existing worktrees.** The reuse path never rebases or fast-forwards (#322
  corner 1). An existing worktree directory short-circuits all of this, as today.

### E. Skills and docs

- `fr-isolation` SKILL.md gets a lifecycle table: container verbs vs worktree verbs,
  and which one applies a changed profile.
- `fr-goal` and `fr-debugging` name `rebuild` as the repair path for a broken
  environment, never `down --force` (#577 acceptance 3). They also state that a
  forced down now preserves the cursor.
- Both mirror generators are re-run: `sync-opencode.py` and `sync-hermes.py`.
- **Minor** version bump: new verbs and new mandatory behaviour.
- The `docs/explainers/fr-isolation.html` page is hand-authored, so it gets an
  in-place edit wherever it names the lifecycle verbs.

## 4. Risks

- **`exec` latency.** Every exec gains one `docker ps` (tens of milliseconds).
  Accepted: that is the price of never failing raw.
- **An auto-resume that surprises.** `exec` against a container someone
  deliberately stopped restarts it. The operator chose this; the stderr notice
  makes it visible.
- **Restoring a stale cursor.** A snapshot that is restored after the branch
  moved on elsewhere could resurrect an old position. Restore never overwrites
  and names what it restored, and a committed cursor on the branch wins because
  it is already present.
- **Cache growth.** One directory per torn-down branch, with small text files.
  `gc`'s empty-dir sweep does not reach it. This is accepted for now and is
  recorded as a known gap, not silently.

## 5. Test Plan

**In this PR:**

1. Unit (`rebuild`): the argv carries `--remove-existing-container`, and
   `--build-no-cache` with `--no-cache`. A missing worktree is refused.
   Host-worktree mode is a no-op and external mode refuses. The state and marker
   are untouched.
2. Unit (`stop`): the argv; the verification re-query; already-stopped is a no-op;
   no container is an error; `status` maps `exited` to `stopped`.
3. Unit (`exec`): running → no resume; stopped or absent → `devcontainer up` then
   exec, with the stderr notice; `docker ps` failure → exit 2 with fr's message;
   resume failure → exit 2 naming `rebuild`.
4. Unit (hazard): an active run in a dirty worktree → `active-run` naming the id
   and cursor, in both `down_refusal` and the `down --all` preview. A finished run
   stays a plain `dirty-worktree`.
5. Unit (preserve): the snapshot copies dirty `docs/superpowers/**` only; the
   tombstone holds every run; a failed snapshot aborts the down with the workspace
   intact; a second teardown merges; restore never overwrites, reports conflicts
   and stamps `restored_at`.
6. Unit (not-found): all four `explain_missing` messages.
7. **Integration** (real git, host-worktree mode, temp repo): `fr run start` →
   `fr isolation down --force` → `fr run advance <id>` prints the torn-down message
   → `fr isolation up --branch <b>` restores → `fr run status <id>` reads it
   (#575 acceptance 4).
8. **Integration** (real git, bare-repo origin): remote-only `<B>` →
   `up --branch <B>` checks out origin's tip; `--base` with `origin/<B>` →
   refused; diverged local/remote → local is used, with the warning.
9. Skill validation, neutrality, and all three mirror tripwires green; version
   lockstep.
10. **Live** (this host, `dev` profile): add a devcontainer feature to the profile
    uncommitted, create an uncommitted scratch file and an active run, `fr isolation
    rebuild`. The new tool answers via `fr isolation exec`; the scratch file
    survives; `fr run status <id>` still reads the cursor (#577 acceptance 1–2).
    Then revert the profile and rebuild again.
11. **Live**: `fr isolation stop` → `status` shows `stopped` → `fr isolation exec
    -- true` auto-resumes, and an in-container install survives (#471).

**Post-merge, operator-driven:** none beyond the version bump reaching installed
clients. Items 10 and 11 are the live walks, done before merge.

## 6. Evidence hygiene

Live walks run against this repo's own `dev` profile and `derio-net/super-fr`,
which is public and `derio-net`-owned. The integration tests use temp repos with
fictional names. No third-party hosts.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-23-lifecycle-container-vs-worktree | `derio-net/super-fr` | `2026-09-23-lifecycle-container-vs-worktree` | — |
