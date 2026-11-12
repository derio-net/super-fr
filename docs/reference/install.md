---
title: "Installing super-fr"
tldr: |
  One command installs the CLI and the plugins. This page has the release channels, what lands on OpenCode and Hermes, and the CLI-only route.
standalone_style: broadsheet
covers:
  - scripts/bootstrap.sh
  - scripts/install.sh
  - packages/fr-opencode-plugin/src/**
reviewed: 2026-11-12 vk compat removal, the page names no removed vk path or env name and isolation up already shows --branch
---

# Installing super-fr

## The one command

```bash
curl -fsSL https://raw.githubusercontent.com/derio-net/super-fr/main/scripts/bootstrap.sh | bash
```

This installs the `fr` CLI, registers and enables the Claude Code plugins, installs the
rules and, when OpenCode or Hermes Agent is present, their skills and slash
commands too. It keeps a managed clone of this repo under `~/.cache/fr/src/super-fr`
(`FR_SRC_DIR` moves it), and running it again updates that clone. To read the script first,
download it with `-o bootstrap.sh` and run `bash bootstrap.sh`.

For Claude Code it registers the `derio-net--super-fr` marketplace and enables
`super-fr@derio-net--super-fr` and `super-fr-dispatch@derio-net--super-fr`.

## Release channels

Pass `--version` after `bash -s --`; every other flag reaches `install.sh`:

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

The installer copies skills and slash commands when `~/.config/opencode` exists; on a fresh
OpenCode setup, set `OPENCODE_SKILLS_INSTALL=1`. It also delivers the super-fr plugin as one
directory, `~/.config/opencode/plugins/fr-opencode-plugin/`, and lists it in `cli.json`'s
`plugins`. The plugin gates file-writing tools outside an isolated workspace, refuses a
base-repo shell command (judged on the whole command line) while a pipeline is live, refuses
a push from a branch whose PR already merged, pins the `fr` binary for the shell, nags once
per session about open acceptance debt, nudges an idle run forward, and draws an fr status
line in the TUI. OpenCode 1.x is not supported: `fr` reports a 1.x session as one it cannot read and
tells you to upgrade.

Both gates find their own `git` from `FR_GIT_CANDIDATES` instead of trusting the `PATH` the
OpenCode server inherited. If git cannot be found, the edit gate allows, since it cannot name
a repository to judge, while the shell gate stays closed for a live pipeline because it
cannot confirm the workspace marker. The plugin warns once at load when no git candidate is
executable, so that allow is never silent.

## Hermes Agent

The installer copies skills and wires hooks and rules when `~/.hermes` exists; set
`HERMES_SKILLS_INSTALL=1` on a fresh setup. What lands where is on the
[Hermes page](hermes.md).

## Just the CLI

```bash
uv tool install 'git+https://github.com/derio-net/super-fr#subdirectory=packages/fr'
```

This gives you `fr` without the plugins, which is enough to read and edit plans and run the
acceptance matrix, but not to run `/fr-goal`.

## Uninstall

`scripts/install.sh --uninstall` removes what the installer added for each harness. If you
installed with the one-liner and have no checkout, the script is in the managed clone:

```bash
bash ~/.cache/fr/src/super-fr/scripts/install.sh --uninstall
```

Requirements are listed on [Components and requirements](components.md).
