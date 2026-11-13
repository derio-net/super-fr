---
title: "Components and requirements"
tldr: |
  The packages super-fr is made of, what each one does, and what has to be installed and logged in before it works.
standalone_style: broadsheet
covers:
  - packages/*/pyproject.toml
  - packages/fr-opencode-plugin/package.json
  - plugins/*/.claude-plugin/plugin.json
reviewed: 2026-11-11 docs-currency phase 5
---

# Components and requirements

## What is in the repository

| Package | What it is |
|---|---|
| `fr` | The CLI: the plan-as-folder engine, tracking on GitHub, GitLab and Gitea, isolation, the run cursor, the acceptance matrix, triage, and `fr hermes` |
| `fr-dispatch` | The runner protocol and tick framework, a library that knows no particular runner |
| `fr-vk` | The VibeKanban runner: an MCP client, card and workspace dispatch, and the bridge daemon |
| `fr-cncd` | The `cncd` runner: a thin HTTP adapter that hands a plan's phases to a cncd daemon's ledger |
| `fr-herdr` | The herdr runner ([herdr control sessions](../herdr-control-sessions.md)): starts `fr triage batch dispatch` runs in a herdr tab |
| `fr-claude-cloud` | The claude-cloud runner: the mailbox the cloud wave driver's agent uses to create, message and archive Claude Code cloud sessions |
| `fr-opencode-plugin` | The OpenCode 2.x plugin: edit and shell gates, push guard, acceptance nag, idle nudge, `fr` pin and a status line |

`plugins/super-fr` and `plugins/super-fr-dispatch` are the Claude Code plugins that carry the
skills, rules and hooks; `plugins/super-fr/hooks/hermes/` holds the Hermes ports of the
isolation guards and the merged-PR push guard. Runners register through the `fr.runners` entry-point group, so adding one
does not mean editing `fr-dispatch`.

## Requirements

- The [superpowers](https://github.com/obra/superpowers) plugin. super-fr wraps its
  brainstorming, test-first and review skills.
- Your repo's forge CLI, logged in: [`gh`](https://cli.github.com/) (the default),
  [`glab`](https://gitlab.com/gitlab-org/cli) or [`tea`](https://gitea.com/gitea/tea).
  Which one is used comes from the `forge:` service in `.devcontainer/fr-profiles.yaml`,
  or from the git remote when that is absent.
- Docker, for the default devcontainer isolation. A host without Docker can isolate with
  a worktree alone (`FR_ISOLATION_TARGET=worktree`).
- [uv](https://docs.astral.sh/uv/), for the `fr` CLI.
- `git`, `jq` and `rsync`: the installer checks for them first and names any that is missing.
- The `devcontainer` CLI, for the default isolation. The installer tries to install it with
  `npm` when it is absent.
- The [VibeKanban](https://github.com/derio-net/vibe-kanban) MCP server, only if you dispatch
  to the `vk` runner. The installer registers `~/bin/vibe-kanban-mcp` when that binary is
  present and skips the MCP setup with a warning when it is not; without the binary on `PATH`,
  `fr-vk` falls back to `npx -y vibe-kanban@latest --mcp`.

## Services

`.devcontainer/fr-profiles.yaml` can declare three services: `forge:`, `ci:` and
`tracking:`, each with a `type` and optionally a `host`. `fr services` (add `--json` for
machines) prints what fr resolved and from where. `fr init scaffold --ci ... --tracking ...`
writes them; `auto` detects, and an inconclusive detection exits 2 naming the flag to pass.
`ci: none` means the local suite is the gate. `tracking: none` means no issues are filed, so
`fr apply --yes` and `fr triage batch dispatch --yes` refuse. Jenkins and Jira are not
supported yet.

## Self-hosted forges

For a self-hosted GitLab, declare `forge: {type: gitlab}` and nothing else: the host comes
from the repo's own git remote. Add `host:` only when the remote's hostname is not the API
host you want. fr passes the resolved host to `glab` as `GITLAB_HOST`, so
`glab auth login --hostname <host>` must already hold a token for it. fr passes a declared GitHub
Enterprise `host:` to `gh` as `GH_HOST`, and refuses a host `gh` is not logged into. `tea` is
not pointed at a self-hosted host yet: fr warns when a Gitea `host:` is declared and leaves the
host to `tea`. Where no repo exists
to read config from, fr reads the forge off a bare URL's path (`/-/merge_requests/` is GitLab,
`/pulls/` Gitea, `/pull/` GitHub); a bare `/issues/N` stays ambiguous by design.
