---
name: fr-isolation
description: >
  Run work in an isolated workspace: git worktree + devcontainer, driven
  through the `fr isolation` CLI (exec-bridge). Use when starting feature
  work that must not touch the base repo, when fr-brainstorming or fr-goal
  needs a workspace, when the operator says "isolate this", "run it in the
  container", or asks to clean up after a merged PR. Requires a devcontainer
  profile (fr-init scaffolds one) — there is no unisolated fallback.
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
- The repo must have at least one devcontainer profile
  (`.devcontainer/<profile>/devcontainer.json`). Missing → `fr isolation`
  exits 2 pointing at fr-init. NEVER proceed unisolated instead; offer the
  fr-init interview (under an autonomous run, treat it as a blocker: pause,
  interview, resume).

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

- `up` resolves the profile (flag → repo default from
  `.devcontainer/fr-profiles.yaml` → sole profile), creates the worktree,
  ensures the host secrets env-file exists, and starts the container with
  the base repo's `.git` mounted at the same absolute path (linked-worktree
  git needs it). One profile per run — changing profile means `down --force`
  and a fresh `up`.

### Cold-start base (#322)

A genuinely NEW branch is cut from a freshly-fetched `origin/<default>`, not
the base repo's current HEAD — so an isolated run never silently inherits the
base checkout's un-merged commits. Reuse (an existing branch or worktree) is
untouched: it keeps that branch's own tip, never rebased.

- default: `git fetch origin`, base on `origin/<default>`. `--base <ref>` bases
  on `<ref>` verbatim, no fetch (`--base HEAD` = fork from current checkout,
  stacking). `--no-fetch` bases on the LOCAL `origin/<default>` ref. No remote
  / fetch fails / ref missing → fallback to local HEAD with a `WARNING`
  naming the base; the run never aborts.

## Exec-bridge discipline

- EVERY build, test, lint, and run command goes through
  `fr isolation exec -- ...`. File edits happen in the worktree directly
  (it's host-visible); execution happens in the container.
- Credential boundary: the container sees only the profile's env-file
  (`~/.config/fr/secrets/<repo>/<profile>.env`) and has NO SSH identity at all
  (deliberately — #377). ALL git-host interaction — `git push`/`fetch` (HTTPS
  **or** SSH), PR/MR creation, `status`/`down`/`gc`'s `gh pr view`/`glab mr
  view`/`tea pulls list` — defaults to the HOST for every backend (`gh`,
  `glab`, `tea`), outside `exec`. A push via `exec` fails with a host-key/
  `Permission denied` (SSH) or auth error (HTTPS) — working as designed;
  re-run from the HOST. `fr isolation status --push-check`: a read-only
  preflight (remotes, in-container SSH-agent visibility — expected absent,
  and the right host-side command).
- Pre-push guard: pushing to a branch whose PR is `MERGED`/`CLOSED` orphans the
  commit from `main` (#320). The `fr-merged-pr-push-guard.sh` PreToolUse hook
  denies it during a pipeline — cherry-pick onto `main` (or a fresh PR) instead.
- The harness resets cwd to the base repo between calls, so host-side git/gh is a
  compound `cd <worktree> && …`; the guard allows a leading `cd` under
  `~/.cache/fr/worktrees` / a temp dir (#279). `up`'s `/add-dir` tip (#281) makes
  a bare `cd` persist. The deny message names every escape. Never run project
  commands against the base repo while isolation is live.
- `up` writes a gitignored `.fr-isolation` marker the `fr-isolation-required`
  PreToolUse hook reads to ALLOW edits; editing tracked files in an fr-enabled
  base clone is blocked (escape: `FR_BASE_OK=1` or `.fr-isolation-allow`).
  `down` removes it. See the fr-isolation-required rule (#328).

## Cleanup contract

The worktree + container PERSIST after the PR is created (the operator may push
to the PR branch — back-loaded manual phases land this way).

- **gc auto-reconciles merged work.** `fr isolation gc` fires detached on every
  `up`/`down` — host-wide, no daemon, ≤1 stale — tearing down MERGED-PR
  workspaces and reaping orphaned containers + dangling `vsc-*` images; open-PR
  and no-PR work is untouched.
- **`down` is the immediate lever** — it verifies the container + worktree are
  actually gone before dropping state (a transient docker failure leaves the
  workspace VISIBLE, never silently leaked) and refuses an open PR unless
  `--force`. fr-goal close-out MAY run it, but no longer must.

## Recovery (#341)

- **Wedged container:** `fr isolation restart [--force]` bounces the
  devcontainer (`docker restart`; `--force` = immediate SIGKILL) WITHOUT
  dropping the worktree / node_modules / in-container installs — prefer it to
  down+up. `fr isolation status --stats` surfaces `docker stats` to spot the thrash first.
- **Orphaned pipeline sentinel** (every base-repo command denied, no worktree
  to `cd` into): the guard self-heals — with zero live worktrees it fails open
  and clears the sentinel. Explicit lever: `fr isolation down --all` tears down
  all workspaces and drops the session sentinel(s).

## Failure handling

`devcontainer up` failures surface verbatim — missing Docker, broken
profile config, or an absent secrets file are operator-environment issues:
report and stop, don't work around isolation.
