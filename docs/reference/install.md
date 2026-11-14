---
title: "Install super-fr"
tldr: |
  One command installs the CLI and the plugins. This page has the release channels, what lands on OpenCode and Hermes, and the CLI-only route.
standalone_style: broadsheet
covers:
  - scripts/bootstrap.sh
  - scripts/install.sh
  - packages/fr-opencode-plugin/src/**
reviewed: 2026-11-13 placement-resolver phase 6 review, the plugin resolves fr from absolute PATH entries and asks it read-only; install delivery and channels are unchanged
---

# Install super-fr

## The one command

```bash
curl -fsSL https://raw.githubusercontent.com/derio-net/super-fr/main/scripts/bootstrap.sh | bash
```

This installs the `fr` CLI, registers and enables the Claude Code plugins, and installs the
rules. When OpenCode or Hermes Agent is present, it also installs their skills and slash
commands. It keeps a managed clone of this repo under `~/.cache/fr/src/super-fr`
(`FR_SRC_DIR` moves it). When you run it again, it updates that clone. To read the script
first, download it with `-o bootstrap.sh` and run `bash bootstrap.sh`.

For Claude Code it registers the `derio-net--super-fr` marketplace and enables
`super-fr@derio-net--super-fr` and `super-fr-dispatch@derio-net--super-fr`.

## Release channels

Pass `--version` after `bash -s --`. Every other flag goes to `install.sh`:

```bash
curl -fsSL https://raw.githubusercontent.com/derio-net/super-fr/main/scripts/bootstrap.sh | bash -s -- --version RC
```

| `--version` | Installs |
|---|---|
| none | the newest release `vX.Y.Z` (`origin/main` if none is installable yet) |
| `RC` | the newest release candidate `vX.Y.Z-rc.N` |
| `X.Y.Z`, `X.Y.Z-RC`, `X.Y.Z-rc.N` | that release, the newest RC of it, or exactly that RC |
| `main` | `origin/main`, the development channel |

An unknown version, or a tag from before channels existed, installs nothing and lists the
installable ones.

## OpenCode (2.x only)

The installer copies skills and slash commands when `~/.config/opencode` exists. On a fresh
OpenCode setup, set `OPENCODE_SKILLS_INSTALL=1`. The installer also delivers the super-fr
plugin as one directory, `~/.config/opencode/plugins/fr-opencode-plugin/`, and lists it in
`cli.json`'s `plugins`.

The plugin gates tools that write files outside an isolated workspace. While a pipeline is live,
it stops a base-repo shell command, and it judges the whole command line. It stops a push from
a branch whose PR already merged. It pins the `fr` binary for the shell. It nags once per
session about open acceptance debt. It nudges an idle run forward, and draws an fr status line
in the TUI.

OpenCode 1.x is not supported. `fr` reports a 1.x session as one that it cannot read, and
tells you to upgrade.

Both gates find their own `git` from `FR_GIT_CANDIDATES`. They do not trust the `PATH` that
the OpenCode server inherited. If git cannot be found, the edit gate lets the edit through,
because it cannot name a repository to judge. The shell gate stays closed for a live
pipeline, because it cannot confirm the workspace marker. The plugin gives one warning at
load when no git candidate is executable, so that pass-through is never silent.

## Hermes Agent

The installer copies skills and wires hooks and rules when `~/.hermes` exists. On a fresh
setup, set `HERMES_SKILLS_INSTALL=1`. What lands where is on the
[Hermes page](hermes.md).

## Just the CLI

```bash
uv tool install 'git+https://github.com/derio-net/super-fr#subdirectory=packages/fr'
```

This gives you `fr` without the plugins. That is enough to read and edit plans and to run
the acceptance matrix, but not to run `/fr-goal`.

## Uninstall

`scripts/install.sh --uninstall` removes the Claude Code rules, fr's worktree hooks and the
`vibe_kanban` MCP entry. It also removes the OpenCode skills, commands, agents and plugin, and
the Hermes hooks, rules and skills.

It leaves the Claude Code plugin registration in `~/.claude/settings.json` in place. It also
leaves the marketplace entry in `~/.claude/plugins/known_marketplaces.json` and the
marketplace clone `~/.claude/plugins/marketplaces/derio-net--super-fr/`. The managed clone
`~/.cache/fr/src/super-fr` and the `fr` CLI stay too. Remove those by hand. If you installed with the one-liner and have no checkout,
the script is in the managed clone:

```bash
bash ~/.cache/fr/src/super-fr/scripts/install.sh --uninstall
```

Requirements are listed on [Components and requirements](components.md).
