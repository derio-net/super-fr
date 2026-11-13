---
title: "Running super-fr under Hermes Agent"
tldr: |
  What the installer puts in a Hermes home, how the isolation guards work there, and how model bindings and phase dispatch differ from Claude Code.
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/commands/hermes_cmd.py
  - packages/fr/src/fr/hermes.py
  - .hermes/config.snippet.yaml
  - plugins/super-fr/hooks/hermes/**
  - HERMES.md
reviewed: 2026-11-12 vk compat removal, the page names no removed vk path or env name and isolation up already shows --branch
---

# Running super-fr under Hermes Agent

super-fr runs on three agent harnesses: Claude Code, OpenCode and
[Hermes Agent](https://github.com/NousResearch/hermes-agent). The skills are the same
everywhere; what differs is how they are installed and how enforcement is wired.

## Install

The installer does this by itself when `~/.hermes` exists. To force it on a fresh Hermes
setup, from a checkout of this repo:

```bash
HERMES_SKILLS_INSTALL=1 bash scripts/install.sh
```

| What | Where | Notes |
|---|---|---|
| Skills | `~/.hermes/skills/fr/<name>/SKILL.md` | invoked as `/fr-goal`, `/fr-plan` and so on |
| Rules | `~/.hermes/SOUL.md` | a delimited `<!-- super-fr:rules START/END -->` block; text outside it is never touched |
| Hooks | `~/.hermes/super-fr-hooks/` | a copied tree; `config.yaml` `hooks:` entries point at it |
| Approvals | `~/.hermes/shell-hooks-allowlist.json` | pre-recorded so runs without a terminal register the hooks without a prompt |

The parts that edit your Hermes config are done by a tested subcommand rather than by shell,
and each is undone by its inverse:

```bash
fr hermes install   --source <super-fr checkout> [--home ~/.hermes]
fr hermes uninstall --source <super-fr checkout> [--home ~/.hermes]
```

`scripts/install.sh --uninstall` calls the second and removes `~/.hermes/skills/fr`. Only
super-fr's own files are touched. `--home` defaults to `$HERMES_HOME`, then `~/.hermes`.

## Enforcement

Hermes accepts a Claude-Code-style block decision, so super-fr ships Hermes versions of the
isolation guards (`plugins/super-fr/hooks/hermes/`) that share the Claude Code hooks' decision
library. Unlike the Claude Code shell guard, the Hermes one judges by the workspace marker on
every git or gh change, not only while a pipeline is live. They gate edits (`write_file`, `patch`) and shell commands
(`terminal`, `execute_code`: git and gh changes outside isolation, and pushes to a merged
PR's branch). A first-turn hook shows open acceptance debt. The escapes are unchanged:
`fr isolation up`, `.fr-isolation-allow`, and `FR_BASE_OK=1`. The rule is explained in
[fr-isolation](../explainers/fr-isolation.md).

## Models and phase dispatch

super-fr ships no Hermes model bindings. `fr models resolve --harness hermes --tier <t>`
prints nothing until you bind one, so `fr-goal` asks which model to use for each tier on its
first run and saves the answer with `fr models set`.

`fr-goal` hands each plan phase to a subagent with `delegate_task(goal, context)`. A Hermes
subagent starts with a fresh conversation, so the whole brief travels in `context`.

Working on this repo with Hermes? [HERMES.md](../../HERMES.md) is the project context file;
it outranks `AGENTS.md`, so read both.
