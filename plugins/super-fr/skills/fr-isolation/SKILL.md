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
fr isolation status [--branch ...] [--format json]              # worktree/container/PR
fr isolation down --branch <feature-branch> [--force]           # post-merge cleanup
```

- `up` resolves the profile (flag → repo default from
  `.devcontainer/fr-profiles.yaml` → sole profile), creates the worktree,
  ensures the host secrets env-file exists, and starts the container with
  the base repo's `.git` mounted at the same absolute path (linked-worktree
  git needs it).
- One profile per run. Pick it once at `up`; changing profile means
  `down --force` and a fresh `up`.

## Exec-bridge discipline

- EVERY build, test, lint, and run command goes through
  `fr isolation exec -- ...`. File edits happen in the worktree directly
  (it's host-visible); execution happens in the container.
- Credential boundary: the container sees only the profile's env-file
  (`~/.config/fr/secrets/<repo>/<profile>.env`). `gh` in-container is
  unauthenticated unless that file provides a token. Push and PR creation
  default to the HOST (run them outside `exec`, from the worktree) — the
  operator's credentials never enter the container implicitly.
- Never run project commands against the base repo while isolation is live;
  the worktree is the only working copy this run touches.

## Cleanup contract

The worktree and container PERSIST after the PR is created — the operator
may push to the PR branch (back-loaded manual phases land this way).

- `fr isolation status` shows the linked PR's state via gh.
- After the PR is observed MERGED, `fr isolation down` cleans up (it
  refuses while the PR is open unless `--force` — protect the operator's
  pending pushes, don't fight the guard).
- Close-out of a fr-goal run includes the `down`.

## Failure handling

`devcontainer up` failures surface verbatim — missing Docker, broken
profile config, or an absent secrets file are operator-environment issues:
report and stop, don't work around isolation.
