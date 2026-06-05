---
name: vk-progress
description: >
  Plan / spec progress reporting. Use when: "what's in progress",
  "status board", "audit drift", "spec rollup", "is this plan up to date".
---

# vk-progress

In v2 there is no dedicated progress subcommand surface. Progress queries
decompose into one of three primitives:

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
PR comment when a PR touching `docs/superpowers/{plans,implemented/plans}/`
merges.

For a single plan, `vk status <plan-dir>` is the read-only deep report:
factual header (created date + age, tick counts, dispatch state),
per-phase table, completion-guard refusals, drift warnings (including
"Issue closed but plan is incomplete" reverse drift), and the archive
nudge. Safe to allowlist — it never mutates.

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

When a plan is finished, archive it with the verb (not a hand-rolled mv):

```bash
vk archive <plan-dir>     # gate-checked git mv to docs/superpowers/implemented/plans/
vk archive --all          # sweep every finished plan; specs follow when all their rows are implemented
```

The gate requires every phase complete (gh evidence, or fully-ticked
never-dispatched); `--force` overrides for a single plan. The owning spec
moves to `implemented/specs/` once all its rows resolve as implemented
(cross-repo rows via the gh contents API). The next `vk spec status` run
re-resolves rows from the new path automatically. The operator still runs
the command and commits the moves — archiving never fires without intent
(the v1 footgun), it's just one verb now instead of a manual mv.

Legacy `archived-plans/` layouts hard-stop every verb until
`vk migrate dirs --yes` runs (one git mv + commit).
