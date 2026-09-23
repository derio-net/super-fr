# fr isolation: separate the container lifecycle from the worktree lifecycle

- **Date:** 2026-09-23
- **Status:** designed (revised after spec review r1)
- **Origin:** gh#577, gh#575, gh#471, gh#438
- **Goal:** each fr isolation verb touches exactly one of the two lifecycles (the
  container or the worktree), and none silently destroys or mis-seeds fr's own
  run record.

## 1. Problem

A workspace has two lifecycles:

- a **worktree**: the branch, the files, the uncommitted run cursor, the
  `.fr-isolation` marker, and the session bindings;
- a **container**: the image, its features, and the running processes.

fr's verbs bundle the two:

| Need | Today | Consequence |
|---|---|---|
| Apply a changed profile (#577) | `restart` is `docker restart` (`local.py:430`); `up` on an existing workspace calls `devcontainer up` without `--remove-existing-container` (`local.py:392`) | The only way to recreate the container is `down --force && up`, which also deletes the worktree |
| Keep the run while repairing (#575) | `down --force` bypasses `_reap_hazard` for every dirty path alike | The uncommitted cursor at `<worktree>/docs/superpowers/runs/<id>.yaml` is deleted. Every `fr run` command then prints `no run state at <path>`, which reads like a mistyped run id |
| Pause an idle container (#471) | No verb exists; `exec` calls `devcontainer exec` with no start step | Operators run `docker stop` by hand, and `exec` then fails with a raw devcontainer error |
| Resume a remote-only branch (#438) | `_git_worktree_add` checks only `git branch --list <B>`, which is local | `origin/<B>` is ignored and a same-named branch is cut from `origin/main`. The worktree silently lacks the branch's commits |

The first two combine into the incident in #575. The container was broken, and
repairing it the only documented way cost a live `/fr-goal` run its cursor and
its pipeline.

## 2. Goal

- **Container verbs** (`stop`, `restart`, `rebuild`, and `exec`'s auto-resume)
  never touch the worktree, branch, marker, bindings or run cursor.
- **Worktree verbs** (`down`, `gc`) name the run they would end. They preserve
  fr's own uncommitted record even when forced, and the next `up` for that branch
  restores it.
- **`up`** seeds a worktree from the branch that already exists, local or remote,
  and names the tip it used. Re-running it on an existing workspace keeps that
  workspace's bindings.

Non-goals:

- `gc --stop-idle`. Idle detection is deferred by the operator; the PR files it as
  a follow-up issue and records that in the PR body.
- Listing containers across repos (the comment on #471).
- Profile switching. That is still `down` + `up --profile`, which is now safe
  because `down` preserves the run.
- Any change to the edit gate or the bash guard. Both already allow every
  `fr isolation …` verb.

## 3. Design

### A. `fr isolation rebuild` (#577)

`fr isolation rebuild [--branch <b>] [--no-cache]` recreates the container
against the existing worktree and the **branch's own** profile config, which is
`<worktree>/.devcontainer/<profile>/devcontainer.json`. A profile fix merged to
`main` applies only once the branch has it. The help text and the report line say
so.

- It runs one shared helper, `_devcontainer_up(worktree, profile, *,
  remove_existing=False, no_cache=False)`, which `up` also uses. The mount and
  config rules therefore cannot drift between the two:

  ```
  devcontainer up --workspace-folder=<wt> --config=<cfg> --mount=<git common dir>
                  [--remove-existing-container] [--build-no-cache]
  ```

- `_ensure_mounted_env_file` runs first. A missing worktree directory is refused
  with "run `fr isolation up`".
- The old container id and image id (via `_image_for`) are captured before the
  rebuild.
- **On success:** it re-queries `docker ps` for the new id and reports
  `isolation rebuild: <b> recreated (<old> → <new>) from <cfg>; worktree
  untouched`. If the image id changed, it runs `_reclaim_image(old_image)`. The
  rebuild retags the same `vsc-…` name, so the old image becomes `<none>`, and
  gc's `vsc-`-prefix sweep would never reach it.
- **On failure:** it raises with devcontainer's output plus the state this left
  behind. `--remove-existing-container` may already have removed the old
  container, so the message says the worktree and run are intact and names
  `fr isolation rebuild` again as the retry. It never reclaims the old image on
  failure.
- The state record, worktree, marker, bindings and cursor are never touched.
- `HostWorktreeTarget.rebuild` prints `nothing to rebuild — host-worktree mode has
  no container` and returns. `ExternalTarget.rebuild` refuses with the existing
  `environment is externally managed` text, as `restart` does.

`restart` keeps its meaning: a process bounce that keeps installs. Its help text
now says it does NOT apply profile changes (use `rebuild`) and that it resumes a
stopped container.

### B. `fr isolation stop` and a stopped-aware `exec` (#471)

- **`stop`.** `fr isolation stop [--branch <b>]` runs `docker stop <id>`, then
  re-queries to verify the container is not running.
  - The worktree, state, marker and bindings are kept.
  - An already-stopped container is a no-op success, and the output says so.
  - With no container at all, it errors with the `up` hint.
  - Host mode prints a no-op message; external mode refuses.
- **`status`.** Docker's `exited` state is shown as `stopped`, in both text and
  JSON. Other states pass through unchanged. The only consumer is
  `tests/unit/test_isolation.py`.
- **`exec`.** Before running, `exec` calls `_ensure_running(state)`, which acts on
  the `docker ps` state:
  - `running` or `restarting`: exec.
  - `exited` or `created`: print `isolation: container for <b> was stopped —
    resuming (devcontainer up)` to stderr, run `_devcontainer_up(...)`, then exec.
    `devcontainer up` is the documented resume path, and it re-runs
    `postStartCommand`, which a bare `docker start` would skip.
  - `paused`: run `docker unpause`, then exec.
  - Absent or `dead`: exit 2 with `no usable container for <b> — \`fr isolation
    rebuild --branch <b>\` recreates it (worktree kept)`. Creating a container from
    scratch is a build, not a resume, so it is never done silently.
  - `docker ps` returns non-zero, or the docker binary is missing
    (`FileNotFoundError`): exit 2 with `docker is unreachable — cannot run in
    <b>`.
  - The resume itself fails: exit 2 naming `fr isolation rebuild`.
- The CLI's `exec` now catches `IsolationError`; before, it caught nothing.

### C. `up` on an existing workspace keeps its record

`up` (and `HostWorktreeTarget.up`) re-saves a fresh `IsolationState` on every
call, which drops `sessions` and `created_at`. When a state record already exists
for the branch, `up` now carries both forward, so advertising `up` as a resume path
cannot unbind other sessions. `log_line` and every new line `up` prints go to
**stderr**. `--print-path` requires that, and `fr run start` shares the output.

### D. Preserve the run record across worktree teardown (#575)

A new module, `fr/isolation/preserve.py`, keeps its data beside the isolation
state in the repo's **git common dir**. That location is repo-scoped (two clones
both named `api` never collide) and reachable from every worktree and from gc's
host-wide sweep through `state.repo_root`:

```
<git-common-dir>/fr/preserved/<sanitized-branch>/
  teardown.json   # {version: 1, branch, worktree, torn_down_at, forced, head,
                  #  runs: [{id, cursor, active, file}],
                  #  files: [{path, base_blob}], deleted: [path], restored_at?}
  files/<repo-relative path>
```

**Run discovery.** `branch_runs(worktree, branch)` reads
`docs/superpowers/runs/*.yaml` with plain `yaml.safe_load`, not the live
`extra="forbid"` model. That keeps old stamps and half-written files readable,
and the function never raises.

- It keeps only files whose `branch:` field equals this workspace's branch.
  `main` carries other branches' run files, and those are not this workspace's
  runs.
- A run is **active** when at least one entry under `steps` has a `state` other
  than `done`.
- A file that cannot be read or parsed counts as active and is labelled
  `unreadable`, never skipped.

1. **Name the run in every refusal.** `_down_worktree_tail` and `down_refusal`
   compute the branch's active runs once. Whichever refusal fires (open PR,
   dirty tree, unlanded content, unverifiable) is prefixed with `holds run <id>
   at step <cursor>`. `down --all`'s blast-radius listing shows the same line even
   under `--force`, where it currently lists nothing. The shared `--force`
   sentence in `_hazard_detail` changes from "uncommitted changes do not survive"
   to "uncommitted changes do not survive, except fr's own records under
   `docs/superpowers/`, which are preserved and restored by the next `up`".
2. **Preserve before destroying (two-phase).** After the guards,
   `_down_worktree_tail` runs `preserve.stage(state)`:
   - It reads `git status --porcelain=v1 -z -uall` in the worktree and copies
     every changed or untracked path under `docs/superpowers/` into `files/`,
     together with that path's `base_blob`, the HEAD blob id from `git rev-parse
     HEAD:<path>` (`null` for an untracked file).
   - A rename counts under its new path. A deletion is not copied; it is listed
     in `deleted`.
   - It returns a `PreserveRecord`. When there is nothing to record (no files,
     no runs of this branch), it writes nothing.
   - `teardown.json` is written **only after** the worktree removal is verified.
     A down that fails later leaves copied files but no tombstone claiming a
     teardown.
   - A stage that cannot copy raises `IsolationError`, and the down aborts with
     the workspace intact. The one escape is `down --force --no-preserve`: an
     explicit, per-call decision to discard the record, for a full disk or an
     unreadable tree.
   - A second teardown of the same branch merges: newer copies win, runs are
     unioned, and a new `head` is recorded. `down`, `down --all` and gc reaps all
     go through the tail, so all of them preserve.
3. **Say it at down time.** `down` returns a `TeardownReport` (`preserved_dir`,
   and `ended_runs: [(id, cursor)]`) on every target. `ExternalTarget.down`
   returns an empty report. `_down_all` and `_reap_or_classify` receive it. The CLI
   prints one line per active run:
   `down: ended run <id> at step <cursor> here — its record is preserved at <dir>;
   \`fr isolation up --branch <b>\` restores it`.
4. **Restore on the next `up`.** When `_git_worktree_add` creates a worktree (never
   when it reuses one), it calls `preserve.restore(repo_root, branch, worktree)`:
   - **Descendant guard.** If the tombstone's `head` is not an ancestor of the new
     worktree's HEAD, the branch was re-created unrelated to the teardown. Nothing
     is restored. A stderr notice names the preserved directory and the two
     commits, and the record stays in place.
   - **Per file:**
     - absent → copy back.
     - present and hashing (`git hash-object`) to the recorded `base_blob` → the
       snapshot is a strict descendant of what is checked out, so overwrite it.
       This is the common case: a committed cursor that later advances made
       dirty.
     - present and identical to the snapshot → nothing to do.
     - anything else → a **conflict**: left in place, reported by path, and the
       copy stays in the cache.
   - A `deleted` path that is present in the checkout at its `base_blob` is
     removed again, so the tree matches its pre-teardown state.
   - The tombstone is stamped `restored_at`, and the stderr line reads
     `isolation: restored N preserved file(s) (run <id> at <cursor>)`.
   - `fr run start` reaches `up` through `ensure_run_workspace` case 3. After a
     restore it refuses a second run for the branch as it always does, and the
     message names `fr run advance <id>` as the way on.
5. **An honest not-found, resolved at the CLI layer.** `load_run_state` stays
   pure (`fr/run/model.py` imports nothing from inside fr). The CLI's
   `_load_or_exit` and the three direct `load_run_state` call sites in
   `run_cmd.py` catch the missing-file case and import `preserve.explain_missing`
   lazily. The checks run in this order:
   1. **A live workspace of this repo holds `runs/<id>.yaml`:** `run <id> lives
      in the workspace at <worktree> (branch <b>) — run fr from there.`
   2. **A tombstone lists the run:**
      - cursor preserved: `run <id> is not in this checkout: its workspace for
        <b> (<worktree>) was torn down at <T>; its record is preserved —
        \`fr isolation up --branch <b>\` restores it, then run fr from there.`
      - cursor committed: the same, ending `its cursor is committed on <b> —
        \`fr isolation up --branch <b>\`, then run fr from there.`
   3. **Otherwise:** `no run <id> at <path>, and fr has no record of one (never
      started here, or a mistyped id). Runs in this checkout: <ids or "none">.`

### E. `up --branch` reuses `origin/<B>` (#438)

The remote probe is a network query, and a failed query is never read as
absence (the #354 invariant). It first probes `git ls-remote --exit-code origin
refs/heads/<B>`:

- exit 0: the branch exists on origin;
- exit 2: the branch is absent;
- anything else: **unknown**.

When the branch exists, fr fetches it with an explicit refspec, `git fetch origin
+refs/heads/<B>:refs/remotes/origin/<B>`. That updates `origin/<B>` even in
`--single-branch` or narrow-refspec clones, which is where pods and CI live.

| local `<B>` | `origin/<B>` | `--base` | Action | Output (stderr) |
|---|---|---|---|---|
| yes | absent, or same tip | any | reuse local | `isolation: reusing local branch <B> at <sha>` |
| yes | local is ahead | any | reuse local | `… at <sha> (N commits ahead of origin/<B>)` |
| yes | local is behind or diverged | any | reuse local (#322 corner 1: never rebase) | `WARNING: local <B> (<sha>) is behind/diverged from origin/<B> (<sha>, +a/−b) — using local; \`git -C <wt> merge --ff-only origin/<B>\` to catch up` |
| yes | unknown | any | reuse local | as the first row, plus `(origin not checked: <reason>)` |
| no | exists | none | `git worktree add --no-track -b <B> <wt> origin/<B>` + `branch.<B>.{remote,merge}` (`--track` refuses a `--single-branch` clone; journal 59d279fcdb7d) | `isolation: reusing remote branch <B> at origin/<B> (<sha>)` |
| no | exists, fetch failed, no local `origin/<B>` ref | any | **refuse** (exit 2) — a cold start here is #438 itself | `origin/<B> exists but could not be fetched (<reason>) — retry, or` `git fetch origin +refs/heads/<B>:refs/remotes/origin/<B>` |
| no | exists | given | **refuse** (exit 2) | `origin/<B> exists — --base would fork a second history under the same name; drop --base to reuse it, or choose another branch name` |
| no | unknown, local `origin/<B>` ref present | none | reuse that ref | WARNING: `origin unreachable — reusing the last-fetched origin/<B> (<sha>); it may be stale` |
| no | unknown, no local ref | any | cold start, as today | the existing `basing new branch …` line with `(<sha>)`, plus a WARNING that origin could not be checked for `<B>` |
| no | absent | any | cold start, as today (#322) | `isolation: basing new branch <B> on <ref> (<sha>)` |

- `--no-fetch` skips the probe and the fetch, and uses a local `origin/<B>` ref
  when one is present.
- With no origin remote, nothing changes from today.
- The local-exists rows fetch only best-effort, so being offline never blocks a
  reuse.
- `_ensure_validator_wrapper_in_ref` is called with the ref actually checked out.

### F. Target protocol changes

- **`Target` (`types.py`)** gains `stop(state) -> str` and `rebuild(state,
  no_cache) -> str`. `down` returns `TeardownReport`.
- **Implementations:**
  - Local: real.
  - Host-worktree: `stop` and `rebuild` are no-op messages. It inherits `down`, so
    it preserves.
  - External: `stop` and `rebuild` refuse; `down` returns an empty report.

  `HostWorktreeTarget` overrides every docker-touching method, so none of the new
  methods ever reaches docker in host mode. A unit test enforces that.

### G. Skills and docs

- `fr-isolation` SKILL.md:
  - the lifecycle command block gains `stop` and `rebuild`;
  - a short "container vs worktree" table says which verb applies a changed
    profile;
  - the "One profile per run — change = `down --force` + `up`" line becomes "a
    changed profile: `rebuild`; a different profile: `down` + `up --profile`, and
    the run record is preserved across it".
- `fr-goal` and `fr-debugging` each gain one sentence: a broken environment is
  repaired with `fr isolation rebuild`, never `down --force`, and a forced down
  preserves the run record (#577 acceptance 3).
- Both mirror generators are re-run: `sync-opencode.py` and `sync-hermes.py`.
- **Minor** version bump.
- The hand-authored `docs/explainers/fr-isolation.html` page is edited in place
  wherever it names the lifecycle verbs.
- **Acceptance rows** (added with the spec, 2026-09-23):
  `isolation-rebuild-keeps-worktree`, `isolation-stop-and-resume`,
  `isolation-down-preserves-run`, `run-missing-explains-teardown` and
  `isolation-up-reuses-remote-branch`. Each moves via `fr acceptance set-status`
  as its evidence lands.

## 4. Risks

- **`exec` latency.** Every exec gains one `docker ps`, tens of milliseconds.
  Accepted: that is the price of never failing with a raw error.
- **A surprising auto-resume.** `exec` against a container that someone
  deliberately stopped starts it again. This was the operator's choice, and the
  stderr notice makes it visible.
- **Restoring the wrong past.** A reused branch name could get stale records
  back. The descendant guard handles it: an unrelated history restores nothing
  and says where the record is.
- **Growth of the preserved directory.** It holds one small directory per
  torn-down branch, and nothing reaps it yet. That is recorded as a known gap
  (a follow-up can age it out via gc), not left silent.

## 5. Test Plan

**In this PR:**

1. **Unit, `rebuild`:**
   - the argv contains `--remove-existing-container`, plus `--build-no-cache`
     with `--no-cache`;
   - a missing worktree is refused;
   - on success the changed old image is reclaimed; on failure it is not, and
     the message names the retry;
   - host mode is a no-op and external mode refuses;
   - the state record and marker are untouched.
2. **Unit, `stop`:**
   - the argv and the verification re-query;
   - an already-stopped container is a no-op;
   - no container is an error;
   - `status` maps `exited` → `stopped`.
3. **Unit, `exec`:**
   - `running` → no resume;
   - `exited` → `devcontainer up`, then exec, with the stderr notice;
   - `paused` → unpause;
   - absent or `dead` → exit 2 naming `rebuild`;
   - a `docker ps` failure or `FileNotFoundError` → exit 2 with fr's message;
   - a resume failure → exit 2.
4. **Unit, naming the run:**
   - an active run of this branch is named in the open-PR, dirty and unlanded
     refusals, and in the `down --all` preview with and without `--force`;
   - a foreign branch's run file is ignored;
   - a finished run is not named;
   - an unparseable or old-schema run file is named as unreadable, and the
     function never raises.
5. **Unit, preserve:**
   - only `docs/superpowers/**` is staged;
   - `-z` parsing handles renames, deletions and a non-ASCII path;
   - the tombstone is written only after a verified removal, so a failed removal
     leaves no tombstone;
   - a stage failure aborts the down, and `--no-preserve` proceeds;
   - a second teardown merges.
6. **Unit, restore:**
   - absent → copied;
   - base-blob match → overwritten;
   - identical → no-op;
   - other → conflict reported and cache kept;
   - `deleted` is re-applied;
   - non-descendant `head` → nothing restored, with a notice;
   - `restored_at` is stamped.
7. **Unit, not-found:** all three orders of `explain_missing`. The live-workspace
   check wins over a tombstone.
8. **Unit, `up`:** re-running `up` on an existing workspace keeps `sessions` and
   `created_at`, and log lines go to stderr.
9. **Integration** (real git, host-worktree mode, temp repo), for #575 acceptance
   4:
   - `fr run start` → commit the cursor → `fr run advance` (now dirty) →
     `fr isolation down` refuses, naming the run;
   - `down --force` prints the ended-run line;
   - `fr run advance <id>` prints the torn-down message;
   - `fr isolation up --branch <b>` restores it, and `fr run status <id>` reads
     the **advanced** cursor.
10. **Integration** (real git, bare-repo origin):
    - a remote-only `<B>` checks out origin's tip;
    - a single-branch clone still finds `<B>`;
    - `--base` together with `origin/<B>` is refused;
    - a behind or diverged local branch is used, with the warning;
    - an unreachable origin with a local ref reuses that ref, with the warning.
11. Skill validation, neutrality, all three mirror tripwires, and version
    lockstep are green.
12. **Live** (this host, the `dev` profile):
    - add a devcontainer feature to the profile uncommitted, with an uncommitted
      scratch file and an active run;
    - run `fr isolation rebuild`;
    - the new tool answers via `fr isolation exec`, the scratch file survives,
      and `fr run status <id>` still reads the cursor (#577 acceptance 1–2);
    - revert the profile and rebuild again.
13. **Live:** `fr isolation stop` → `status` shows `stopped` → `fr isolation exec
    -- <cmd>` auto-resumes, and an in-container install survives (#471 acceptance
    1–3).

**Post-merge, operator-driven:** nothing beyond the version reaching installed
clients. Items 12 and 13 are the live walks, done before merge.

## 6. Evidence hygiene

The live walks run against this repo's own `dev` profile and
`derio-net/super-fr`, which is public and `derio-net`-owned. The integration
tests use temp repos with fictional names. No third-party hosts are involved.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-23-lifecycle-container-vs-worktree | `derio-net/super-fr` | `2026-09-23-lifecycle-container-vs-worktree` | — |
