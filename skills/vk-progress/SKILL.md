---
name: vk-progress
description: >
  Plan / spec progress reporting. Use when: "what's in progress",
  "status board", "audit drift", "spec rollup", "is this plan up to date".
---

# vk-progress

In v2 there is no separate `vk progress` subcommand surface. Progress
queries decompose into one of three primitives:

| Operator says | Command |
|---|---|
| "audit drift on this plan" | `vk apply <plan-dir>` (default dry-run lists what gh would change) |
| "status of this spec" | `vk spec status <spec-path>` |
| "status of every spec" | `vk spec status --all` |
| "mark step done" | `vk plan edit <plan-dir> --tick P<n>.T<n>.S<n>` |
| "mark phase done" | `vk plan edit <plan-dir> --complete-phase N [--note ...]` |

**Announce at start:** "I'm using vk-progress for [capability]."

## How it works (no separate state store)

`vk` is a single state machine: the plan files (`_meta.yaml` + `NN.yaml`) are
the source of truth, and every projection (Issue body / labels / state, spec
table row) is computed on demand. There is nothing to "sync" — `vk apply`
diffs the projection against observed gh state and emits the mutations
needed to bring them in line. `vk spec status` walks the plan folders
referenced by the spec table and rolls up step / phase counts.

## Audit drift on a plan

```bash
vk apply <plan-dir>             # default: dry-run; prints what would change
vk apply <plan-dir> --yes       # apply the changes
vk apply --all                  # walk every plan in docs/superpowers/plans/
vk apply <plan-dir> --format json   # machine-readable
```

If the diff is empty, plan and gh are in sync. If it's non-empty, you have
an actionable list of label / state / body changes.

## Spec rollup

```bash
vk spec status <spec-path>      # one spec
vk spec status --all            # every spec in docs/superpowers/specs/
```

Output is markdown: per-plan state (Not Started / In Progress / Complete /
Missing / Unreachable), step + phase counts, and an aggregate. Cross-repo
plans surface as `Unreachable` in this layer (a future cross-repo lookup
will resolve them via the gh contents API).

The reusable `.github/workflows/vk-spec-status.yml` posts this output as a
PR comment when a PR touching `docs/superpowers/{plans,archived-plans}/`
merges.

## Tick / complete phases

```bash
vk plan edit <plan-dir> --tick P<n>.T<n>.S<n> --state x
vk plan edit <plan-dir> --tick P<n>.T<n>.S<n> --state - --note "<reason>"
vk plan edit <plan-dir> --complete-phase N
vk plan edit <plan-dir> --complete-phase N --note "ran <runbook ref>"  # required for manual phases
```

`--tick` is idempotent on re-tick; `--complete-phase` refuses agentic phases
with unticked steps (use rework for deferred items — see `vk-plan`).

## Archive-on-complete

When the operator decides a plan folder should move to
`docs/superpowers/archived-plans/`, do it as an explicit `git mv`:

```bash
git mv docs/superpowers/plans/<slug>/ docs/superpowers/archived-plans/<slug>/
```

The next `vk spec status` run will re-resolve the row from the new path.
There is no automated archiver in v2 — keeping the move explicit avoids the
v1 footgun where archiving fired without operator intent.
