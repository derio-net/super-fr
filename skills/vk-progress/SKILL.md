---
name: vk-progress
description: >
  Work lifecycle tracking. Use when: "sync progress", "status board",
  "what's in progress", "audit", "transition state", "health summary".
---

# vk-progress

Five subcommands, auto-detecting dispatch/local mode.

**Announce at start:** "I'm using vk-progress for [capability]."

## Triage

| Operator says | Subcommand |
|---|---|
| "sync progress", "update the plan" | `vk progress sync <plan> --yes` |
| "status board", "what's in progress" | `vk progress board` |
| "create work item", "new bug" | `vk progress create <title> --type <type>` |
| "move to deployed", "mark complete" | `vk progress transition <target> <state> --yes` |
| "audit", "what's stale" | `vk progress audit` |

## Modes

| Capability | Dispatch enabled | Local mode |
|---|---|---|
| Sync | Issues -> checkboxes -> spec index | Checkboxes -> Status -> spec index |
| Board | Query project board | Scan local plan files |
| Create | Create GitHub Issue | Unavailable (gate refusal) |
| Transition | Move lifecycle state | Edit Status header |
| Audit | Full drift checks + Grafana | Local drift checks only |

All subcommands use `--dry-run`/`--yes` contract.
