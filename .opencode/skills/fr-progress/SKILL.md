---
name: fr-progress
description: >
  Plan / spec progress reporting. Use when: "what's in progress",
  "status board", "audit drift", "spec rollup", "is this plan up to date".
---

# fr-progress

In v2 there is no dedicated progress subcommand surface. Progress queries
decompose into one of three primitives:

| Operator says | Command |
|---|---|
| "audit drift on this plan" | `fr apply <plan-dir>` (default dry-run lists what gh would change) |
| "status of this spec" | `fr spec status <spec-path>` |
| "status of every spec" | `fr spec status --all` |
| "mark step done" | `fr plan edit <plan-dir> --tick P<n>.T<n>.S<n>` |
| "mark phase done" | `fr plan edit <plan-dir> --complete-phase N [--note ...]` |

**Announce at start:** "I'm using fr-progress for [capability]."

## How it works (no separate state store)

`vk` is a single state machine: the plan files (`_meta.yaml` + `NN.yaml`) are
the source of truth, and every projection (Issue body / labels / state, spec
table row) is computed on demand. There is nothing to "sync" — `fr apply`
diffs the projection against observed gh state and emits the mutations
needed to bring them in line. `fr spec status` walks the plan folders
referenced by the spec table and rolls up step / phase counts.

## Audit drift on a plan

```bash
fr apply <plan-dir>             # default: dry-run; prints what would change
fr apply <plan-dir> --yes       # apply the changes
fr apply --all                  # walk every plan in docs/superpowers/plans/
fr apply <plan-dir> --format json   # machine-readable
```

If the diff is empty, plan and gh are in sync. If it's non-empty, you have
an actionable list of label / state / body changes.

## Spec rollup

```bash
fr spec status <spec-path>      # one spec
fr spec status --all            # every spec in docs/superpowers/specs/
```

Output is markdown: per-plan state (Not Started / In Progress / Complete /
Missing / Unreachable), step + phase counts, and an aggregate. Cross-repo
plans are resolved via the gh contents API (the same capability `fr archive`
uses) — their remote phase files are read and given the same phase/step
counts as a local plan, so they count toward the aggregate. Pass `--no-gh`
(or run offline) and cross-repo rows degrade to `Unreachable`.

The reusable `.github/workflows/fr-spec-status.yml` posts this output as a
PR comment when a PR touching `docs/superpowers/{plans,implemented/plans}/`
merges.

For a single plan, `fr status <plan-dir>` is the read-only deep report:
factual header (created date + age, tick counts, dispatch state),
per-phase table, completion-guard refusals, drift warnings (including
"Issue closed but plan is incomplete" reverse drift), and the archive
nudge. Safe to allowlist — it never mutates.

## Acceptance debt

`fr acceptance status` — counts by status + the open `skipped` /
`not-implemented` rows (backfill owed, oldest first); `--brief` is the capped
session-start form. `fr status <plan-dir>` appends the same one-line summary
when the repo has `docs/acceptance/matrix.yaml`. Gate: `fr acceptance check`
(exit 2 on `failing` rows). See the `fr-acceptance` skill for backfill.

## Tick / complete phases

```bash
fr plan edit <plan-dir> --tick P<n>.T<n>.S<n> --state x
fr plan edit <plan-dir> --tick P<n>.T<n>.S<n> --state - --note "<reason>"
fr plan edit <plan-dir> --complete-phase N
fr plan edit <plan-dir> --complete-phase N --note "ran <runbook ref>"  # required for manual phases
```

`--tick` is idempotent on re-tick; `--complete-phase` refuses agentic phases
with unticked steps (use rework for deferred items — see `fr-plan`).

## Archive-on-complete

When a plan is finished, archive it with the verb (not a hand-rolled mv):

```bash
fr archive <plan-dir>     # gate-checked git mv to docs/superpowers/implemented/plans/
fr archive --all          # sweep every finished plan; specs follow when all their rows are implemented
```

The gate requires every phase complete (gh evidence, or fully-ticked
never-dispatched); `--force` overrides for a single plan. The owning spec
moves to `implemented/specs/` once all its rows resolve as implemented
(cross-repo rows via the gh contents API). The next `fr spec status` run
re-resolves rows from the new path automatically. The operator still runs
the command and commits the moves — archiving never fires without intent
(the v1 footgun), it's just one verb now instead of a manual mv.

Rows reported Unreachable/Missing for plans that exist locally mean
stale refs (pre-2.5.0 path forms). Normalize them idempotently:
`fr repair` previews, `fr repair --yes` rewrites File cells and
`_meta.yaml` refs to bare slugs, warning loudly about anything it
cannot resolve. `fr archive` / `fr migrate dirs` run the same repair
in passing.

Legacy `archived-plans/` layouts hard-stop every verb until
`fr migrate dirs --yes` runs (one git mv + commit).
