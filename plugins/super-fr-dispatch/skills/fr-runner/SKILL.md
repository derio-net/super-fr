---
name: fr-runner
description: >
  Operate and debug an autonomous runner (the VibeKanban adapter today):
  verify tick health, diagnose stuck or undispatched phases, recover
  orphan workspaces, and read the dispatch metrics. Use when queued
  phases aren't being picked up, when the operator asks "why didn't this
  dispatch", "is the bridge alive", "check the runner", or after a pod
  upgrade to confirm the daemon still ticks.
---

# fr-runner

The runner is the autonomous consumer of queued phases. The framework
surface is `fr_dispatch` (`discover_plans` + `tick` against the Runner
protocol); the VibeKanban adapter is `fr_vk` (`VkRunner`, MCP client,
card/workspace creation, the cron daemon `python -m fr_vk.bridge`).
Neither is wired into the `fr` CLI — the daemon consumes them as a
library on its pod.

## Health checks

1. **Is the daemon ticking?** The heartbeat gauge
   (`willikins_heartbeat_last_success_timestamp`) must be recent.
   Sync/failure counters: `willikins_vk_bridge_sync_total`,
   `willikins_vk_bridge_failure_total{reason=…}` — reasons:
   `project_id_missing`, `unknown_repo`, `mcp_error`, `gh_error`.
2. **Is a phase eligible?** `fr status <plan-dir>` on the plan: a phase
   dispatches only when its RENDERED labels say ready-but-not-synced,
   it has a `tracking_issue`, and the plan + spec are on origin/HEAD
   (the bridge pod pulls; reachability is why dispatch requires merged
   plans).
3. **Repo known to the runner?** The VK adapter refuses repos its board
   doesn't list (`unknown_repo` failures) — add the repo in VK first.

## Common faults

- **Queued forever, no failures:** pod checkout stale (pull the repo on
  the pod), or every slot is in use (workspace budget — the runner
  defers and retries next tick, no action needed).
- **`project_id_missing`:** the pod env lost `VK_DERIO_OPS_PROJECT_ID`.
- **Dispatched in error:** `fr undispatch <plan-dir> --yes` closes the
  Issues and nulls the tracking fields; the runner's reaper archives
  the orphan workspaces on its next pass.
- **Card exists, workspace missing:** set
  `VK_BRIDGE_RECOVER_ORPHAN_CARDS=1` for one tick (opt-in recovery).

## Boundaries

This skill OPERATES runners; queueing work to them is `fr-dispatch`'s
ceremony, and implementing phases is `fr-execute`'s. The daemon never
creates Issues (operator-only via `fr apply --yes`) and never implements
work itself.
