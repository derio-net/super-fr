# vk-isolation suite — isolated, containerized autonomous runs

**Date:** 2026-06-04
**Status:** Approved (autonomous run; operator delegated design approval via /vk-goal)
**Tracking:** single PR, spec + plan + implementation together

## Problem

Autonomous runs (vk-goal) currently work directly in the operator's clone, or
in ad-hoc worktrees with no environment guarantees. Three gaps:

1. **No enforced workspace isolation.** A run can touch the base repo
   (checkouts, stashes, half-finished state) and collides with the operator's
   own work. Worktree usage is convention, not contract.
2. **No environment isolation.** Commands run on the host with the operator's
   full credentials and toolchain — every run is implicitly "admin".
3. **No reproducible per-repo environment.** Each run rediscovers tools,
   credentials, and working patterns; nothing captures "how you work in this
   repo" as configuration.

Additionally, `vk skills` crashes (`ModuleNotFoundError: No module named
'click'`): `skills_cmd.py` imports click directly but pyproject does not
declare it; the uv tool environment resolves typer without exposing click.

## Solution shape

Three new skills plus CLI support, layered:

```
vk-goal ──▶ vk-brainstorming ──▶ vk-isolation ──▶ [worktree + devcontainer]
                  │                    ▲
                  └── (no container?)  │ requires .devcontainer/<profile>/
                        HARD STOP ──▶ vk-init (interview, scaffolds profiles)
```

- **vk-isolation** — pluggable isolation target. v1 target: git worktree +
  devcontainer (exec-bridge). CLI: `vk isolation up/exec/down/status`.
- **vk-init** — interactive interview that scaffolds one or more committed
  devcontainer *profiles* for a repo, plus host-side secrets files.
- **vk-brainstorming** — wraps `superpowers:brainstorming`; enters isolation
  BEFORE exploration, so the base repo is never touched from the first
  command on.

## Decisions (operator Q&A, 2026-06-04)

### vk-isolation

- **Exec-bridge execution model.** The driving session stays where it is;
  every command runs inside the container via `devcontainer exec` against
  the worktree mount. File edits land in the worktree (host-visible).
  **Agent-agnostic requirement:** the CLI surface is plain shell — any
  agent (Claude, Gemini CLI, Copilot CLI) or a human can drive it; nothing
  in `vk isolation` may assume a specific agent. A nested-agent-in-container
  model is a future pluggable target, out of scope here.
- **Skill + CLI surface.** Mechanical parts live in `vk isolation`
  subcommands with a pluggable `Target` abstraction
  (`LocalWorktreeDevcontainerTarget` now; remote pod later). Conversational
  parts live in `skills/vk-isolation/SKILL.md`.
- **Cleanup at post-merge close-out.** Worktree + container persist after PR
  creation (the operator may push to the PR, e.g. back-loaded manual
  phases). `vk isolation status` reports worktree, container, and PR state
  (via `gh pr view`). `vk isolation down` tears down. No background watcher.
- **Profile selection:** `vk isolation up --profile <name>`, defaulting to
  the repo's configured default profile. One profile per vk-goal run.
- **Hard requirements:** must run inside a git repo; the repo must have at
  least one devcontainer profile. Missing either → exit 2 with a message
  pointing at vk-init. Never silently degrade to unisolated.

### vk-init

- **Profiles are committed:** `.devcontainer/<profile>/devcontainer.json`
  (native devcontainer-CLI multi-config layout). Shareable and reviewable.
  The default profile is recorded in `.devcontainer/vk-profiles.yaml`
  (`default: <name>`, plus per-profile metadata: purpose, secrets file
  expected keys). Single-profile repos still use the named-subfolder layout
  so a second profile is an add, not a migration.
- **Secrets via host env-file mount:** each profile's devcontainer.json
  wires `"runArgs": ["--env-file", "${localEnv:HOME}/.config/vk/secrets/<repo>/<profile>.env"]`.
  vk-init scaffolds that file with commented placeholders for every key the
  interview surfaces. Secrets never enter the repo or the image. Read-only
  vs admin profiles differ in their env-file contents (credentials), not
  (necessarily) their tool set.
- **Baseline tooling in every profile:** git, gh, and the vk CLI, plus
  whatever the repo scan + interview adds (uv, node, kubectl, …) via
  devcontainer features where available.
- **Interview is interactive by design** — questions about working
  patterns, credentials, tools. Under an autonomous vk-goal run, a missing
  devcontainer is treated like any other blocker: the run pauses, the
  interview happens, the run resumes isolated. First run per repo pays once.

### vk-brainstorming

- **Isolation begins at brainstorm start.** `vk isolation up` is the first
  action; exploration, spec, plan, implementation all happen inside.
- **Standalone = interactive, still isolated.** The batched-Q&A contract
  applies only when vk-goal drives.
- **No devcontainer → HARD STOP.** Offer to run the vk-init interview;
  without it, vk-brainstorming refuses. There is no unisolated fallback.
- **Trigger wiring:** `rules/vk-plan-override.md` gains a Brainstorming
  Override (feature brainstorms in a repo with vk plans or devcontainer
  profiles route to vk-brainstorming); vk-goal step 1 invokes
  vk-brainstorming.

## CLI surface (mechanical layer)

```
vk isolation up [--profile NAME] [--branch BRANCH] [--path DIR]
    # worktree add (default: ~/.cache/vk/worktrees/<repo>/<branch> — outside
    # the repo, so no gitignore entry is required of host repos) + devcontainer
    # up against it. State recorded in <base>/.git/vk/isolation/<branch>.json
    # (.git is never committable). Verifies the profile's secrets env-file
    # exists (creates an empty one if missing — docker refuses a missing
    # --env-file).
vk isolation exec [--branch BRANCH] -- CMD ...
    # devcontainer exec in the isolation workspace (exit code passthrough)
vk isolation status [--format text|json]
    # worktree path/branch, container state, linked PR state via gh
vk isolation down [--force]
    # devcontainer stop/rm + worktree remove; refuses if PR open unless --force
vk init scaffold --profile NAME --purpose TEXT [--tool T ...] [--secret KEY ...] [--default]
    # mechanical writer: devcontainer.json + vk-profiles.yaml entry + host
    # env-file with placeholders; the SKILL drives the interview, then calls this
```

`Target` is a small protocol (`up/exec/down/status`) so a future
`RemotePodTarget` plugs in without CLI changes.

### Git inside the container (worktree mechanics)

A linked worktree's `.git` is a FILE whose gitdir points at
`<base>/.git/worktrees/<name>` by absolute path — mounting only the worktree
folder leaves git broken inside the container. `vk isolation up` therefore
ALSO mounts the base repo's `.git` directory read-write at the same absolute
path (extra `--mount` to `devcontainer up`). Credential boundary: git works
in-container; `gh` is installed but unauthenticated unless the profile's
env-file provides a token (admin profiles may; read-only ones don't). Push
and PR creation default to the HOST side — the operator's credentials never
enter the container implicitly.

## Skill changes

- `skills/vk-isolation/SKILL.md` (new) — lifecycle contract, exec-bridge
  discipline ("every build/test/run command goes through `vk isolation
  exec`"), cleanup rules.
- `skills/vk-init/SKILL.md` (new) — repo scan first (languages, manifests,
  CI, existing .devcontainer), then interview (working patterns, tools,
  credentials, profiles wanted), then `vk init scaffold` per profile.
  Multi-profile aware from day one (e.g. read-only vs admin).
- `skills/vk-brainstorming/SKILL.md` (new) — wraps brainstorming inside
  isolation; hard-stop contract; hands off to vk-plan as before.
- `skills/vk-goal/SKILL.md` (edit) — step 1 invokes vk-brainstorming
  (which brings isolation); step 6 drops its own worktree handling in
  favor of the already-active isolation workspace; step 9 adds
  `vk isolation down` to close-out.
- `rules/vk-plan-override.md` (edit) — Brainstorming Override section.
- `skills_cmd.py` SKILLS list — add the three new skills.

## Bug fix

- pyproject `dependencies` gains `click>=8` (skills_cmd imports it
  directly; declaring it is correct regardless of typer's resolution).
  Regression test: invoking the skills command must not raise.

## Out of scope

- Nested-agent-in-container target (future Target implementation).
- Remote pod target.
- Per-phase profile mapping (plans tagging phases with profiles).
- Automatic PR-merge watching/daemons.
- Migrating existing repos' workflows to isolation (adoption is per-repo
  via vk-init).

## Test Plan (post-merge — operator-driven)

1. Install 2.4.0 (`scripts/install.sh`), restart Claude Code.
2. `vk skills` prints the command/skill overview (bug fixed, three new
   skills listed).
3. In superpowers-for-vk: run `/vk-init`, create a `dev` profile (default)
   — verify `.devcontainer/dev/devcontainer.json`,
   `.devcontainer/vk-profiles.yaml`, and
   `~/.config/vk/secrets/superpowers-for-vk/dev.env` placeholders exist.
4. `vk isolation up` → worktree under `.worktrees/`, container running;
   `vk isolation exec -- vk --version` prints inside-container version;
   base repo `git status` untouched.
5. `vk isolation status` shows workspace + container + no PR; after a
   trivial branch PR, shows the PR; `vk isolation down` refuses while the
   PR is open, `--force` cleans up.
6. `/vk-brainstorming` in a repo WITHOUT a devcontainer → hard stop
   offering vk-init.

## Implementation Plans

| Plan | Repo | File | Depends on |
| --- | --- | --- | --- |
| 2026-06-04-vk-isolation-suite | `derio-net/superpowers-for-vk` | `docs/superpowers/archived-plans/2026-06-04-vk-isolation-suite/` | — |
