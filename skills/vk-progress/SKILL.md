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

## Spec Index Reconciliation

`sync` always reconciles the spec index, even when the plan's Status header is already correct.
This handles the case where a plan was updated (e.g., by a VK workspace agent) but the spec's
`## Implementation Plans` table wasn't. Running `vk progress sync` on any plan with a `**Spec:**`
header will bring the spec index row in line with the plan's current status.

## Archive-on-Complete

When `sync` flips Status to `Complete`, it interactively offers to move the plan
file to `docs/superpowers/archived-plans/`:

- Interactive: prompts `"Plan is Complete. Archive ... [y/N]"`
- `--yes`: archives without prompt.
- `--dry-run`: prints `"Would archive: <src> -> <dest>"`.

The destination is set by `profile.plan.archive_to` in `plan-config.yaml`
(default `docs/superpowers/archived-plans/`). The spec index row is updated
to point at the new archived path.
