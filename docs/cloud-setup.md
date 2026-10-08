# fr in a Claude Code cloud session

A Claude Code cloud session runs in a container prepared by its **environment's setup
script**. Every new session runs that script before its first turn; a session that is
already running does not. A new session can also be a pre-warmed spare whose script ran
before the latest release, so its `fr` may be older than the release (measured by the
2026-10-08 live walk, derio-net/super-fr#1098): check `fr --version` first. fr relies on
the script for four things, and on the repo for a fifth (spec
`docs/superpowers/implemented/specs/2026-10-07-cloud-triage-design.md`, R19-R23, §H).

| Prerequisite | Why | Fixed by |
|---|---|---|
| `forge.api: rest` in `~/.config/fr/forge.yaml` | the cloud proxy refuses GitHub's GraphQL API (HTTP 403) | the setup script |
| the super-fr plugin registered in `~/.claude/plugins/installed_plugins.json` | the skills and hooks | the setup script |
| a current `fr` | the session's CLI is whatever the script installed | a new session |
| `rsync` | `scripts/install.sh` copies the plugin with it | the setup script |
| the repo's `agents` artifact | the plugin's agents are not dispatchable in a fresh session | `fr init agents` |

## The setup script

Print it with `fr cloud setup-script` and paste the output into the environment
(the cloud environment menu in a session's title bar, then **Edit**, then **Setup
script**), or create a new environment with it. fr never runs it: it is environment
configuration, and this document deliberately carries no copy of it, so the two cannot
drift. In order, it:

1. installs `rsync` and `jq` (`apt-get`) and `uv` when missing;
2. seeds `~/.claude/plugins/installed_plugins.json` (`{"version":2,"plugins":{}}`) and
   `~/.claude/settings.json` (`{}`) when absent: a fresh container has neither, and
   `scripts/install.sh` now **fails**, naming the missing file, rather than warning and
   exiting 0 without registering the plugin;
3. clones super-fr's `main` into `~/.cache/fr/src/super-fr` (outside the marketplace
   directory, which `install.sh` replaces) and runs its `scripts/install.sh`;
4. writes `api: rest` to `~/.config/fr/forge.yaml`.

Then start a new session: it runs the script, the one you are in does not.

## Checking an environment

`fr cloud doctor` lists every prerequisite above with its state and fix, and exits 1
when any fails. In a cloud session (`CLAUDE_CODE_REMOTE=true`, which the harness sets in
every shell) an fr command that fails for one of these reasons — a GraphQL 403 under
`forge.api: graphql`, a worker blocked on the `agents` artifact, a run cursor written by a
newer fr — ends with one block naming what is missing and this fix. On a host none of
this ever prints.

## The `agents` artifact

A cloud session's CLI is a pre-warmed spare that loaded its agent types before the setup
script ran, so the plugin's `super-fr:fr-spec-reviewer` and `super-fr:fr-phase-executor`
are not dispatchable in it; the same agents committed under the repo's
`.claude/agents/` are, from the first turn. `fr init agents` renders both there, each
the canonical agent with one added front-matter key, `fr_artifact_version`, and commits
them (`fr init scaffold` does the same). They are an artifact kind like the others: `fr
validate artifacts` fails one that is missing, unstamped, misnamed or stale, and a
release that changes either agent moves the kind's version, so the repo's CI stays red
until `fr migrate artifacts --yes` re-renders them. A host session sees both the plugin's
and the repo's names, which is harmless: fr's gates accept either.

A worker session (a batch dispatched through the `claude-cloud` runner) checks this
first: `fr --version` (installing super-fr only when `fr` is missing), then that both
agent types are dispatchable. When they are not, it ends its turn BLOCKED with a
`needs_action` naming the artifact, and is not re-homed: a new session from the same
commit would start the same way. A worker enters isolation through the CLI (`fr
isolation up`), so isolation never depends on the plugin's hooks.

## The cloud driver

The wave driver runs as a long-lived cloud session (the fr-triage skill's **cloud
driver** paragraph), on a model the operator sets (Sonnet by default). Its brief carries
a host id and the scope's state repo. **The first step of every wake** writes that host id
to `~/.config/fr/host-id` and `api: rest` to `~/.config/fr/forge.yaml` when either file
is missing: each tool call is a fresh shell and a container restart loses both, and the
host id is the driver's identity (`cloud:<host id>`, the holder of the scope's drive
lease, and the input of its scope id), so a fresh container derives the same scope and
renews its own lease instead of being refused by it. The wake then runs `fr triage drive
pass` with the scope's arguments, executes the outbox it writes (session requests only
its agent can make), records the results with `fr triage drive record`, and schedules
the next wake. A re-homed driver's brief carries the same host id. The cloud driver runs
no `post_merge`: every session it starts installs the current release through the setup
script, and the driver updates itself before each pass (R18, R20).
