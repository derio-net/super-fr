---
title: "fr in a Claude Code cloud session"
tldr: |
  A Claude Code cloud session runs in a container prepared by its environment's setup script. This page says what fr relies on that script and the repo for, and how to check it.
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/cloud.py
  - packages/fr/src/fr/commands/cloud_cmd.py
reviewed: 2026-11-11 docs-currency phase 3
---

# fr in a Claude Code cloud session

A Claude Code cloud session runs in a container that its **environment's setup
script** prepares. Every new session runs that script before its first turn. A session
that already runs does not run it again. A new session can also be a pre-warmed spare
whose script ran before the latest release. Its `fr` can then be older than the release
(the 2026-10-08 live walk measured this, derio-net/super-fr#1098). So check `fr --version` first.

fr relies on the script for four things, and on the repo for two more (spec
`docs/superpowers/implemented/specs/2026-10-07-cloud-triage-design.md`, R19-R23, §H).

| Prerequisite | Why | Fixed by |
|---|---|---|
| `forge.api: rest` in `~/.config/fr/forge.yaml` | the cloud proxy does not accept GitHub's GraphQL API (HTTP 403) | the setup script |
| the super-fr plugin registered in `~/.claude/plugins/installed_plugins.json` | the skills and hooks | the setup script |
| a current `fr` | the session's CLI is the one that the script installed | a new session |
| `rsync` | `scripts/install.sh` copies the plugin with it | the setup script |
| the repo's `agents` artifact | the plugin's agents are not dispatchable in a fresh session | `fr init agents` |
| a merge method the driver may use | under `forge.api: rest` the driver sees no default merge method, so in a repo that lets you use several methods, the driver stops every merge | `merge_method` in `.fr/triage.yaml` |

## The setup script

Print it with `fr cloud setup-script`. Paste the output into the environment: open the
cloud environment menu in a session's title bar, then **Edit**, then **Setup script**.
Or make a new environment with it. fr never runs the script, because it is environment
configuration. This document intentionally has no copy of it, so the two cannot drift.
In this order, the script:

1. installs `rsync` and `jq` (`apt-get`), and `uv` when it is not there;
2. seeds `~/.claude/plugins/installed_plugins.json` (`{"version":2,"plugins":{}}`) and
   `~/.claude/settings.json` (`{}`) when they are absent. A fresh container has neither file.
   `scripts/install.sh` now **fails** and names the absent file. It does not warn
   and exit 0 without a registered plugin;
3. clones super-fr's `main` into `~/.cache/fr/src/super-fr` and runs its `scripts/install.sh`.
   The clone is outside the marketplace directory, because `install.sh` replaces that directory;
4. writes `api: rest` to `~/.config/fr/forge.yaml`.

Then start a new session. The new session runs the script; the session you are in does not.

## Check an environment

`fr cloud doctor` lists every prerequisite above with its state. It prints the fix for each
one that fails, and exits 1 when any fails. In a cloud session it then prints the remedy
block for the failed ones other than the merge method.

In a cloud session, `CLAUDE_CODE_REMOTE=true` is set in every shell by the harness. There,
some fr commands fail for one of these reasons: a GraphQL 403 under `forge.api: graphql`, or a run
cursor that a newer fr wrote. Such a command ends with one block that names what is not
there and this fix. A worker that stops on the `agents` artifact quotes the same block in its
`needs_action`. On a host, none of this ever prints.

## The `agents` artifact

A cloud session's CLI is a pre-warmed spare. It loaded its agent types before the setup
script ran. So the plugin's `super-fr:fr-spec-reviewer` and `super-fr:fr-phase-executor`
are not dispatchable in it. The same agents, committed under the repo's `.claude/agents/`,
are dispatchable from the first turn.

`fr init agents` renders both there and commits them.
Each one is the canonical agent with one more front-matter key, `fr_artifact_version`.
`fr init scaffold` does the same.

They are an artifact kind like the others. `fr
validate artifacts` fails one that is absent, unstamped, misnamed or stale. A release that
changes either agent moves the kind's version. The repo's CI then stays red until
`fr migrate artifacts --yes` renders them again. A host session sees both the plugin's names and the repo's names. That
does no harm, because fr's gates accept either.

A worker session (a batch dispatched through the `claude-cloud` runner) checks this
first. It runs `fr --version`, then reads the `fr` line of `fr cloud doctor`. It runs the setup
script again when `fr` is not there or is older than the latest release (as on a pre-warmed
spare). Then it checks that it can run the batch's skill (`/fr-goal`, or `/fr-debugging` for
a debug batch). It reads the skill from the plugin's installed copy when the session did not
load it. Then it checks that both agent types are dispatchable (a file under
`.claude/agents/` is not proof).

When one of these checks fails, the worker ends its turn BLOCKED, with a `needs_action` that
names what is not there. It is not re-homed: a new session from the same commit starts the
same way. A worker never does the batch's work without its skill, because a PR with no run is a false
success.

The worker enters isolation through the CLI (`fr isolation up`), so isolation never
depends on the plugin's hooks. In a cloud session (`CLAUDE_CODE_REMOTE=true`), `fr
isolation up` selects the docker-less host-worktree mode by default, as
`FR_ISOLATION_TARGET=worktree` does.

## The cloud driver

The wave driver runs as a long-lived cloud session (see the **cloud driver** paragraph of the
fr-triage skill). It runs on a model that the operator sets (Sonnet by default). Its brief
contains a host id and the scope's state repo.

**The first step of every wake** writes that host id to `~/.config/fr/host-id`, and
`api: rest` to `~/.config/fr/forge.yaml`, when either file is not there. The reason: each
tool call is a fresh shell, and a container restart loses both files. The host id is the
identity of the driver (`cloud:<host id>`). It is the holder of the scope's drive lease, and
the input of its scope id. So a fresh container gets the same scope and renews its own
lease. The lease does not stop it.

The wake then runs `fr triage drive
pass` with the scope's arguments. It executes the outbox that the pass writes (session
requests that only its agent can make). It records the results with `fr triage drive record`,
and schedules the next wake. The brief of a re-homed driver contains the same host id.

The cloud driver runs no `post_merge`. Every session it starts installs the current release
through the setup script, and the driver updates itself before each pass (R18, R20). In a
cloud session, that in-place update prints no "restart the session to re-pin" warning.

The driver's clone is its own, so it needs no manual setup. When `origin/HEAD` is not set,
fr asks origin for the default branch (`git remote set-head origin --auto`). Before a
close-out, the driver checks out the default branch when the clone is detached or on
another branch. It never switches a clone that has local changes; it does not accept that clone.

A close-out session starts on the default branch, because the batch branch was deleted
when its PR merged. A session whose start failed (its `last_init_error`) shows as blocked,
with the error as its note, never as "working". A pass that restored the state from its ref
says so.
