---
title: "fr-dispatch: Handing Phases to a Machine That Works Alone"
date: 2026-11-11
draft: false
tldr: |
  Dispatch turns a plan's phases into GitHub issues a runner can pick up, and keeps
  those issues in step with the plan as it changes. A runner takes the queued phases
  through one shared contract, so the steps are the same for every runner.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr-dispatch/skills/fr-dispatch/SKILL.md
  - packages/fr/src/fr/commands/apply_cmd.py
  - packages/fr/src/fr/commands/undispatch_cmd.py
  - packages/fr-dispatch/src/**
reviewed: 2026-11-14 VK support removed; the fr-runner skill is gone, the examples use the cncd runner
---

## Why does the plan stay the source of truth?

You wrote a plan. Now you want something else, a runner on another machine, to work on
its phases while you do something different. fr's answer is the GitHub issue. Each phase
of a plan becomes one issue. Its body embeds the spec link, the plan's prose and the
phase's own YAML, and its labels say where it stands. A runner watches for issues
labelled as queued for it.

fr stores nothing twice. The plan files are the truth. fr computes the issue body and
labels from them on demand, and compares them with what GitHub actually shows. One
command, `fr apply`, does the render, the observe, the diff and the mutations. The same
command handles first creation, incremental updates and ongoing reconciliation. There is
no separate "first dispatch" verb.

You reach for it when you want a plan's phases tracked as issues, queued to a runner, or
brought back in line after you edited the plan. This is a different path from
[fr-goal](01-fr-goal.md), which runs a whole feature to one pull request in one
workspace. Dispatch is for phase-sized work handed to someone or something else.

## A worked example

```bash
fr status docs/superpowers/plans/2026-11-11-webhook-limiter
fr apply  docs/superpowers/plans/2026-11-11-webhook-limiter
```

`fr status` is the read-only audit. A locally complete plan shows "would refuse create":
it is done, so archive it instead of dispatching it. `fr apply` with no flag is a **dry
run**. It lists what it would do: ensure labels, create an issue, edit labels, edit a
body, set a state. Read the preview, then act.

The plan and its spec must already be on the default branch, because the runner works
from its own checkout of it. Otherwise this exits 2 (see "What do you check before you dispatch?" below):

```bash
fr apply docs/superpowers/plans/2026-11-11-webhook-limiter --to cncd --yes
```

`--to cncd` queues the phases. It adds `fr:ready` and `runner:cncd` labels, checks the
runner name against the registered runners, and enforces the reachability gate. It also
refuses a runner that does not take phases, before it calls the forge (see "Which runners
are there?" below). `--yes` applies.
Afterwards fr prints the URLs of the issues it created. It stages the `tracking_issue`
line into each affected phase file.

Commit and push that change, and name the issue URLs in the
commit body. Then the runner's checkout can see them, and you have a trail if a dispatch
turns out to be wrong.

## How does tracking differ from queueing?

Plain `fr apply` is **tracking only**: it records attribute labels so GitHub mirrors the
plan, and queues nothing. Queueing is explicit, with `--to <runner>`. The runner choice
lives on the issue as a label, never in the plan files, and mixing runners per phase is
legal. To take a phase back, `fr undispatch <plan-dir> --yes` closes the issues (reason:
not planned) and nulls the tracking fields. Without `--yes`, it previews.

The issue then moves through labels that fr derives from what GitHub shows:

- `fr:blocked` while a phase it depends on is not complete;
- `fr:ready` with no assignee and no open PR;
- `fr:in-progress` with an assignee or a draft PR;
- `fr:pr-ready` with an open, non-draft PR;
- closed once the plan records completion *and* fr observes a merged PR.

A `[manual]` phase closes once its completion records a time and a note, with no PR. That
is why `fr apply` is safe to run before a PR merges: it can only set `pr-ready` then.

A repo can opt out of these writes in its `.fr/settings.yaml`. Under `forge.issues: off`
or `forge.labels: off`, `fr apply --yes` refuses with exit 2, and the dry run warns that
it would. Under `forge.issues: off`, `fr undispatch --yes` refuses with exit 2 too. The
bridge skips each kind of write (labels or issues) that is off for the repo. See
[the dispatch lifecycle reference](../reference/dispatch-lifecycle.md).

## What do you check before you dispatch?

1. **Audit** with `fr status <plan-dir>`. Spec rows marked Unreachable for plans that
   exist locally are stale references; `fr repair --yes` normalises them.
2. **For a plan never dispatched, look for work that already landed.** Search the target
   repo for merged pull requests that match the plan's slug, and read the file at each
   deliverable path. If the work is there, stop and reconcile with the operator. This
   check exists because a plan with nothing ticked once had fifteen merged PRs behind it.
3. **Merge the plan and its spec first.** A remote runner pulls the repo, so `fr apply --yes
   --to` refuses (exit 2, listing the unreachable paths) unless both are on the default
   branch. Open a PR for spec and plan, merge it, and make the dispatch writeback a
   second, small PR. If you have never run `git remote set-head origin --auto`, `apply`
   tells you to.

## What do the exit codes mean?

| Exit | Meaning | What to do |
|---|---|---|
| 0 | success, or nothing to change | relay any issue URLs |
| 2 | usage error, completion-guard refusal, or legacy layout | read the message; `fr archive` a finished plan, `--force` to override, `fr migrate dirs --yes` for the layout |
| 4 | forge CLI or network failure | check the forge CLI's auth and retry |
| 5 | the plan failed to parse | inspect the plan files |

`fr apply --format json` gives the machine-readable form, and an empty diff means in sync.

## How does a runner take a queued phase?

The runner is the autonomous consumer of queued phases. The framework half is the
`fr_dispatch` package. Its `tick` function discovers the eligible items and hands each one
to a runner through the `Runner` protocol. Runners register through the `fr.runners`
entry-point group, so adding one edits no existing package.

`tick` is a library function, not an `fr` command: a runner's own bridge process calls it
on a schedule. `fr apply --to` and `fr triage batch dispatch` call other parts of
`fr_dispatch` (its runner registry, item graph and reachability gate).

When a queued phase sits still, work through these, in order:

1. **Is the bridge ticking?** A bridge that passes `tick` a metrics pusher stamps a
   heartbeat gauge, `<namespace>_heartbeat_last_success_timestamp`, at the end of each
   tick. Each failure increments `<namespace>_failure_total` with a `reason`:
   `preflight` (the runner refused the whole tick, for example `cncd` with no
   `CNCD_URL`), `repo_gate`, `unknown_repo` (the runner refused the item, usually because
   of its repo), `unit_mismatch`, `backend_error` or `gh_error`. Plan discovery adds `stale_artifact` for
   a plan whose files this `fr` cannot read.
   `unit_mismatch` means an issue has the label of a runner that never takes that unit.
   `fr apply --to` refuses that up front, so look for labels set by hand or by an older
   `fr`.
2. **Is the phase eligible?** `fr status <plan-dir>`. A phase dispatches only when its
   rendered labels say ready-but-not-synced, it has a `tracking_issue`, and plan and spec
   are on the default branch.
3. **Dispatched in error?** `fr undispatch <plan-dir> --yes` closes the issues. It leaves
   the runner's own records alone: reaping them is the runner's job.

## Which runners are there?

The repo ships three adapters. `cncd` (the CNC control plane) takes phases, so it is the
one `fr apply --to` queues to. `herdr` and `claude-cloud` take whole runs only, so
`fr apply --to` refuses them. The triage batch driver uses those two to start whole-run
sessions. See [fr-triage](fr-triage.md), the [herdr guide](../herdr-control-sessions.md)
and the [cloud guide](../cloud-setup.md).

## What does dispatch not do?

- A runner's bridge never creates issues (only `fr apply --yes` does, at an operator's command),
  and never implements work itself.
- Dispatch needs the plan and spec merged first. That is a feature: the runner works from
  its own checkout.
- Operating a runner is not queueing to it, and neither is implementing the phase. See
  [fr-brainstorming-and-plan](fr-brainstorming-and-plan.md) for what the executor does.

## Where do you go next?

- [fr-progress](fr-progress.md) for the read-only audit commands.
- [fr-brainstorming-and-plan](fr-brainstorming-and-plan.md) for authoring the plan you
  dispatch.
