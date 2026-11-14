---
title: "fr-isolation: The Sandbox an Agent Can't Walk Out Of"
date: 2026-11-11
draft: false
tldr: |
  super-fr promises a reviewed PR built in a workspace that never touches your
  checkout. fr-isolation is what makes "never" literally true: not a request in a
  prompt, but a boundary enforced at the tool layer, on every single edit.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-isolation/SKILL.md
  - plugins/super-fr/rules/fr-isolation-required.md
  - plugins/super-fr/hooks/fr-isolation-required.sh
  - plugins/super-fr/hooks/fr-isolation-guard.sh
  - packages/fr/src/fr/isolation/**
reviewed: 2026-11-13 placement-resolver phase 6 review, no fr on a plain repo, a trusted bounded read-only fr, one switch spelling (R26)
---

## What are the two boundaries and the bridge?

Hand an autonomous agent write access to your real checkout and two things go wrong
fast: it collides with your in-flight work, and its generated commands inherit your full
credentials. fr-isolation removes both by construction.

fr nests every run inside two independent boundaries. A **git worktree**, a throwaway
copy of the repo physically outside your clone, absorbs all the checkouts, stashes and
commits. A **devcontainer** wraps execution, so generated code only ever sees the
credentials the workspace's profile explicitly grants. File edits land on the host-visible
worktree. One command, the exec-bridge, funnels everything runnable into the container.

You do not ask for isolation. It is the only door in.

Two docker-less modes sit beside the default, for hosts and pods with no container
runtime. The **host-worktree** mode (`FR_ISOLATION_TARGET=worktree`) has the worktree and
the host's own environment, and no profile. In the **external** mode, the environment's
preparer writes the marker itself and fr adopts it. The worktree boundary and the edit gate
are the same in all three.

## Where does the work live, and where does it run?

The base checkout is never a participant. Edits happen on the worktree, and the
exec-bridge proxies execution into the sealed container. A small marker file ties the whole
thing to the enforcement layer.

```mermaid
flowchart LR
  subgraph host[Your machine - host]
    base[Base checkout: your clone]
    wt[Private worktree<br/>edits land here]
  end
  subgraph box[Sealed devcontainer]
    run[build, test, lint, run]
  end
  base -. never edited .-> wt
  wt -- fr isolation exec --> run
  wt --- marker[.fr-isolation marker]
```

| Boundary | What it is | What it guarantees |
|---|---|---|
| Workspace isolation | A real linked worktree cut from the committed tree, at `~/.cache/fr/worktrees/<repo>/<branch>`: its own branch, outside the base clone. | Your clone is never touched. |
| Environment isolation | A sealed devcontainer started from a committed profile, with scoped credentials only: no SSH identity and no git-host tokens unless the profile grants them, so a push cannot originate here. Before `up` reports it ready, fr also runs `fr --version` inside it, so a failed tool install stops startup there. | The agent only holds what the workspace was granted. |

The marker closes the loop. On `up`, fr writes `.fr-isolation` into the worktree root and
adds it to the repo's exclude list: gitignored, never committed, backed by a CI tripwire.
A hook checks every edit the agent attempts against it.

The marker also records where fr keeps its own records for this workspace. You choose the
**stealth** placement with `fr isolation up --stealth <tracking-repo>@<branch>`, or with
`--target <path>` from a clone of the tracking repository. The marker then carries
`placement: stealth` and the tracking ref. fr keeps the run's records in a clone of that
separate repository at `~/.cache/fr/worktrees/<repo>/stealth--<tracking-slug>` instead of
on your branch.

`up` refuses before creating anything when it cannot reach the tracking repository, when
that repository lacks the branch, or when it is more visible than the target.
`--resume <run-id>` brings a stealth run up on another host. The
[fr-goal explainer](01-fr-goal.md) tells the whole story.

## Who creates worktrees?

Four things can create a worktree. fr owns or routes all of them, and knows which agent
session holds each workspace.

| Creator | Location | State and session link |
|---|---|---|
| `fr isolation up` | `~/.cache/fr/worktrees/<main-checkout>/<branch-slug>`, keyed on the main checkout even when run from inside another worktree | `<common-dir>/fr/isolation/<slug>.json`, plus a per-session index at `~/.cache/fr/sessions/<session-id>.json` |
| Claude Code's own worktree commands (`claude --worktree <name>`, `EnterWorktree`) | the same fr location, on branch `wt/<name>`, because the plugin's `WorktreeCreate` hook calls `fr isolation up` | fr state, with the session bound in the same call |
| A subagent started with `isolation: "worktree"` (`agent-*` names) | `~/.cache/fr/agent-worktrees/<main-checkout>/agent-<id>`, a detached worktree outside the repo | none; `fr isolation gc` removes the finished, clean ones |
| superpowers' `using-git-worktrees` | routed to `fr isolation up` by the shipped rule `fr-worktree-override.md`; `<repo>/.worktrees/` is never created | fr state |

`fr isolation status` lists the sessions holding each workspace. The shipped script
`plugins/super-fr/scripts/fr-statusline-segment.sh` prints the branch a session works on and
its worktree, green when it is an fr workspace and purple when not.
`fr-statusline-claude.sh` is a ready-made Claude Code status line built on that script.

In the default devcontainer mode, a repo with no profile is a stop, not a degraded mode (the
two docker-less modes above need none). The `fr-init` skill scans the repo, interviews you
about tools, credentials and working patterns, and scaffolds the profiles with
`fr init scaffold`. You pay that once per repo. And `fr isolation down` refuses
while the branch's PR is still open unless you pass `--force`, so cleanup cannot race your
final pushes.

## Why can't a faked marker get past the gate?

A `PreToolUse` hook runs on every edit tool call, in any session, forever. It accepts an
edit only if the marker survives a series of descending checks, each one written to defeat
a specific way of cheating. (On OpenCode and Hermes the same decision runs from their own
hook points; while a pipeline is live, a sibling guard judges the shell.)

1. **Is there a `.fr-isolation` marker at the file's git root?** If not, and the path is
   not on the allow-list, the hook refuses the edit outright.
2. **Does the marker's recorded root match the actual root?** This defeats a worktree
   copied elsewhere: the recorded path no longer resolves to here.
3. **Is the mode one fr knows?** `worktree` (devcontainer or host-worktree) and `external`
   are valid; anything unknown or mistyped fails closed instead of slipping through.
4. **Does the mode's own check pass?** For `worktree`, the toplevel must be a genuine linked
   worktree (`git-common-dir` differs from `git-dir`), which defeats a marker copied into
   your base clone, where those two paths are identical, so even a byte-perfect forgery
   fails. For `external`, the toplevel match must come with container evidence
   (`/.dockerenv`, `/run/.containerenv` or `$KUBERNETES_SERVICE_HOST`), so a marker forged
   on a bare host never validates.
5. **For `worktree`: is HEAD still on the marker's branch?** This defeats a workspace that
   drifted: a `git checkout -b` inside it leaves fr's state describing one branch while you
   edit another. A detached HEAD, as in the middle of a rebase, still passes, and nothing
   blocks the way back (`git switch <registered branch>`).

Before step 1 the hook asks whether the repo is fr-enabled at all. That answer is not only
"has a devcontainer profile or a plans directory". A repo on the **quiet** placement keeps
neither in its checkout, so the hook also reads the switch directly. It looks for the last
fetched `origin/fr` carrying `placement: quiet` (and a repo with an origin remote), or a
workspace whose marker records `placement: quiet` or `stealth`.

The switch has exactly one spelling, the line `placement: quiet`, which
`fr settings init --quiet` writes and fr itself insists on. The hook skips a commented-out
line, and no live line naming placement means repo. Any other live spelling (quoted, with a
trailing comment, indented, in flow style, written twice) counts as quiet. So an odd
spelling closes the gate rather than opening it. These direct reads need no `fr`.

A plain repo stops there and starts no `fr` at all, which keeps every edit fast. Only when
an `origin/fr` ref exists does the hook ask `fr settings paths --no-create`. A timeout bounds
that call, and it is read-only: it never creates the `fr` branch or worktree. The hook runs
it only from an `fr` in an absolute PATH entry, never one a relative entry could find inside
the repo. A missing, failing, slow or garbled `fr` can therefore only fail to add a "yes",
never turn one into a "no", so the gate is never weaker for lack of the binary. The OpenCode
plugin and the Hermes hook make the same decision (one shared definition each).

Only a marker that clears every step allows the edit, with one structural exception. Under
quiet and stealth, fr keeps a feature's spec, plan and journals outside the workspace: in the
repo's own `fr` worktree, or in the clone of the tracking repo. Neither carries a marker, so
the gate recognises them by their shape instead.

The `fr` worktree must be a linked worktree of the same repository, at exactly the path fr
gives it (`~/.cache/fr/worktrees/<repo>/fr`), on branch `fr`, while the switch says
`placement: quiet`. A worktree of another repo parked at that path, or a branch named `fr`
anywhere else, does not qualify. The tracking clone must have a `stealth--…` name, sit
beside a workspace whose marker is valid and says `placement: stealth`, and have the origin
and branch that marker names. The skills ask `fr settings paths --shell` for the directories
(`FR_SPECS_DIR`, `FR_PLANS_DIR` and the rest) rather than writing to `docs/superpowers/` in
the workspace.

There are three ways around the gate, all deliberate:

- **`FR_BASE_OK=1`**: a one-shot environment override for a deliberate, knowing edit to the
  base clone.
- **`.fr-isolation-allow`**: a root glob-list for operator-managed paths (data, caches,
  memory) that legitimately live outside isolation.
- **Self-heal**: the Bash guard's sentinel records every workspace your session bound. It
  stays armed while any survives, and retires once they are all gone, so it never
  deadlocks you.

The gate answers one question only: is this fr work happening in an fr-enabled repo's base
clone instead of its workspace? It is not a filesystem sandbox or a credential boundary,
and it says nothing about paths outside an fr-enabled repo.

## Which three shipped bugs shaped the design?

Nobody designed the sharp edges of isolation in the abstract. They are fixes, and the
design docs say so.

- **Committed, not written: the profile has to be on the branch.** A worktree is cut from
  the committed tree. A devcontainer profile that existed only on disk, never
  committed, silently vanished from the worktree, surfacing as a cryptic "config not
  found". Scaffolding now commits the profile by default; a write-only escape stays for the
  rare case.
- **Trust reality, not exit codes: teardown re-queries the world.** An early version
  believed docker's return codes and always deleted its state, so a transient hiccup left
  22+ orphaned containers across the operator's machine, invisible to `status`. Teardown
  now re-checks the actual post-condition: gone means gone, regardless of what an exit
  code claimed.
- **No new daemon: garbage collection without a scheduler.** "I don't want another
  scheduler on each host." So there is no cron. Instead every `up` and `down` fires a
  detached, best-effort sweep. Steady-state leakage stays at most one stale
  workspace, host-wide, the accepted price of keeping the system daemon-free.

## How do you drive the boundary by hand?

The lifecycle is a plain-shell CLI any agent or human runs identically: edits on the host,
every command through the bridge.

```bash
fr isolation up --branch feat/rate-limit --profile dev   # worktree + container
fr isolation exec --branch feat/rate-limit -- uv run pytest -q
fr isolation status                                      # worktree, container, PR
fr isolation stop --branch feat/rate-limit               # free the container; the next exec resumes it
fr isolation rebuild --branch feat/rate-limit            # profile changed: new container, same worktree
fr isolation down --branch feat/rate-limit               # after the PR merges
```

The container is disposable; the worktree is the work. So the verbs that touch only the
container (`restart`, `stop`, `rebuild`) never touch your uncommitted files or the run's
cursor, and a changed profile is a rebuild, not a teardown. Even a forced `down` keeps fr's
own records under `docs/superpowers/` (unless you pass `--no-preserve`). It preserves them
inside the repository's git directory, and the `up --branch` that re-creates the worktree
puts them back.

The restore only ever adds. When a file changed since the teardown, fr reports it as a
conflict and keeps the preserved copy. The restore reports a recorded deletion but never
re-applies it, and a different branch re-created under the same name gets nothing.

Or watch the boundary bite with no container at all: in any isolation-enabled repo, have an
agent edit a tracked file from the base clone with no active workspace. The hook refuses it
before the write touches disk. That single denial is the whole thesis: the sandbox is not a
suggestion the agent can drift out of, it is a gate it cannot walk around.

Back to the [fr overview](index.md).
