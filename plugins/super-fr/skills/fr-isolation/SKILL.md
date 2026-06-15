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
- Credential boundary: an `env-file` profile (the default) makes its declared
  secrets ambient in the container via the mounted
  `~/.config/fr/secrets/<repo>/<profile>.env`. Push and PR creation default to
  the HOST (run them outside `exec`, from the worktree) — the operator's
  credentials never enter the container implicitly.
- On-demand secrets (`infisical` profiles): most commands need no secret; for a
  command that does, request it explicitly — `fr isolation exec --secret KEY
  [--secret KEY2] -- CMD` (repeatable). The value is fetched at runtime
  (path-scoped) and injected into that one command's env; it is never printed to
  stdout/transcript/logs, and the bootstrap token never lands on any argv. A
  `--secret` key must be declared in the profile's `secrets:` (fail-fast).
- ALL GitHub interaction relies on an AUTHENTICATED HOST: pushes, PR
  creation, and `fr isolation status`/`down`'s PR checks (`gh pr view`)
  all use the host's gh/git auth. The container needs NO GitHub token for
  the standard pipeline — never ask the operator for one to make
  isolation work. A non-default profile may carry *other* in-container
  credentials (e.g. `KUBECONFIG_B64`, a deploy/registry token), but gh
  itself stays host-side — a container GH_TOKEN is not a thing here.
- The Claude Code harness resets the persistent shell cwd back to the base
  repo between calls, so every host-side git/gh op is a compound
  `cd <worktree> && gh …` / `cd <worktree> && git push`. The isolation
  guard explicitly allows a leading `cd` whose target resolves under
  `~/.cache/fr/worktrees` or a temp dir (#279) — nothing else leaves the
  base-repo cwd. To stop the resets entirely, `fr isolation up` prints an
  `/add-dir <worktree>` tip in a Claude Code session (#281); run that slash
  command once and the worktree becomes an allowed working directory, after
  which a bare `cd <worktree>` persists and the `cd <worktree> &&` prefix is
  no longer needed — the compound form stays as the fallback before the dir
  is added.
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
