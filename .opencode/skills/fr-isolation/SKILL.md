---
name: fr-isolation
description: >
  Run work in an isolated workspace: git worktree + devcontainer, driven
  through the `fr isolation` CLI (exec-bridge). Use when starting feature
  work that must not touch the base repo, when fr-brainstorming or fr-goal
  needs a workspace, when the operator says "isolate this", "run it in the
  container", or asks to clean up after a merged PR. devcontainer mode needs a
  profile (fr-init scaffolds one); host/external modes run docker-less.
---

# fr-isolation

A workspace contract, not just a worktree: code lives in a git worktree
OUTSIDE the repo (`~/.cache/fr/worktrees/<repo>/<branch>`), commands run
inside the profile's devcontainer, and the base repo is never touched while
the run is live. The surface is plain shell — any agent or a human drives it
identically; nothing here assumes a specific agent.

**Announce at start:** "I'm using fr-isolation to run this work isolated."

## Hard requirements

- Must run inside a git repo.
- **devcontainer mode** (default) needs ≥1 devcontainer profile
  (`.devcontainer/<profile>/devcontainer.json`). Missing → `fr isolation`
  exits 2 pointing at fr-init. NEVER proceed unisolated; offer the fr-init
  interview (autonomous run: pause, interview, resume).

### Modes (`FR_ISOLATION_TARGET`) — host env / docker-less

Same worktree + exec-bridge contract in all three; only the environment half
differs (the profile requirement is a devcontainer-mode rule, not isolation's).

- **host-worktree** (`=worktree`): fr worktree, the host process env as-is — NO
  profile, no secrets provisioning (pods carry their own creds). A host-level
  declaration (pod/image env), never a per-call flag.
- **external** (valid preparer-written `.fr-isolation` marker, `mode:external`):
  fr adopts the container's checkout — `up --branch` just ensures the branch in
  place; restart/stats refuse (the container's owner restarts it).

Unknown `FR_ISOLATION_TARGET` fails closed naming `devcontainer|worktree`.

## Lifecycle

```bash
fr isolation up --branch <feature-branch> [--profile <name>]   # worktree + container
fr isolation exec --branch <feature-branch> -- CMD ...          # every build/test/run
fr isolation status [--branch ...] [--format json] [--stats] [--push-check]  # state; --stats: docker resource use; --push-check: remotes + host-push guidance
fr isolation restart [--branch ...] [--force]                   # bounce a wedged container, worktree kept
fr isolation down --branch <feature-branch> [--force]           # immediate teardown (verifies + reaps image)
fr isolation down --all [--force]                               # tear down ALL + clear pipeline sentinel(s)
fr isolation gc [--dry-run] [--format json]                     # host-wide: reap merged workspaces + dangling images
```

- `up` (devcontainer mode) resolves the profile (flag → repo default from
  `.devcontainer/fr-profiles.yaml` → sole profile), creates the worktree,
  ensures the host secrets env-file exists, and starts the container with the
  base repo's `.git` mounted at the same absolute path (linked-worktree git
  needs it). One profile per run — change means `down --force` + fresh `up`.

### Cold-start base (#322)

A genuinely NEW branch is cut from freshly-fetched `origin/<default>`, not the
base repo's HEAD — an isolated run never silently inherits the base checkout's
un-merged commits. Reuse (existing branch/worktree) keeps that branch's own tip.

- default: `git fetch origin`, base on `origin/<default>`. `--base <ref>` bases
  on `<ref>` verbatim, no fetch (`--base HEAD` = fork from current checkout).
  `--no-fetch` uses the LOCAL `origin/<default>`. No remote / fetch fails / ref
  missing → fallback to local HEAD with a `WARNING`; the run never aborts.

## Exec-bridge discipline

- EVERY build/test/lint/run command goes through `fr isolation exec -- ...`; file
  edits happen in the worktree directly (host-visible), execution in-container.
- Credential boundary (devcontainer mode): the container sees only the profile's
  env-file (`~/.config/fr/secrets/<repo>/<profile>.env`), NO SSH identity (#377).
  ALL git-host interaction — push/fetch, PR/MR creation, `gh`/`glab`/`tea` reads
  in `status`/`down`/`gc` — defaults to the HOST outside `exec` (a push via
  `exec` fails by design; re-run from the HOST; `status --push-check` previews).
  Host/external modes inherit the ambient env — the environment owner's concern.
- Pre-push guard: pushing to a branch whose PR is `MERGED`/`CLOSED` orphans the
  commit from `main` (#320); `fr-merged-pr-push-guard.sh` denies it — cherry-pick
  onto `main` (or a fresh PR) instead.
- The harness resets cwd to base each call, so host-side git/gh is compound `cd
  <worktree> && …`; the guard allows a leading `cd` under `~/.cache/fr/worktrees`
  / temp (#279); `/add-dir` (#281) persists a bare `cd`. Never run base commands.
- `up` writes a gitignored `.fr-isolation` marker (`mode` records which of the
  three modes) the `fr-isolation-required` PreToolUse hook reads to ALLOW edits;
  editing tracked files in an fr-enabled base clone is blocked (`FR_BASE_OK=1` /
  `.fr-isolation-allow` escape). `down` removes it. See that rule (#328).

## Cleanup contract

The worktree + container PERSIST after the PR is created (the operator may push
to the PR branch — back-loaded manual phases land here).

- **gc auto-reconciles merged work.** `fr isolation gc` fires detached on every
  `up`/`down` — host-wide, no daemon, ≤1 stale — tearing down MERGED-PR
  workspaces + reaping orphaned containers/dangling `vsc-*` images; open-PR and
  no-PR work untouched.
- **`down` is the immediate lever** — verifies container + worktree are gone
  before dropping state (a transient docker failure leaves the workspace
  VISIBLE, never leaked) and refuses an open PR unless `--force`.

## Recovery (#341)

- **Wedged container:** `fr isolation restart [--force]` bounces the devcontainer
  (`docker restart`; `--force` = SIGKILL) WITHOUT dropping the worktree /
  installs — prefer it to down+up. `status --stats` shows `docker stats` first.
- **Orphaned pipeline sentinel** (every base-repo command denied, no worktree to
  `cd` into): the guard self-heals — zero live worktrees → fails open, clears the
  sentinel. Explicit lever: `fr isolation down --all` tears down all + sentinels.

## Failure handling

`devcontainer up` failures surface verbatim — missing Docker, broken profile
config, or an absent secrets file are operator-environment issues: report and
stop, don't work around isolation (no silent degradation to a weaker mode).
