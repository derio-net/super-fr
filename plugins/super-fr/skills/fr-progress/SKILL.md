---
name: fr-progress
description: >
  Plan / spec progress reporting, and the repo-state preflight for any repo
  with docs/superpowers/ or fr config. Use when: "what's in progress",
  "status board", "audit drift", "spec rollup", "is this plan up to date",
  "is this repo fr-managed", "legacy v1 plans", "before archiving or moving
  files under docs/superpowers/".
---

# fr-progress

In v2 there is no dedicated progress subcommand surface — queries decompose into one of three primitives:

| Operator says | Command |
|---|---|
| "audit drift on this plan" | `fr apply <plan-dir>` (default dry-run lists what gh would change) |
| "status of this spec" | `fr spec status <spec-path>` |
| "status of every spec" | `fr spec status --all` |
| "mark step done" | `fr plan edit <plan-dir> --tick P<n>.T<n>.S<n>` |
| "mark phase done" | `fr plan edit <plan-dir> --complete-phase N [--note ...]` |

**Announce at start:** "I'm using fr-progress for [capability]."

## Repo-state preflight (run before touching docs/superpowers/ by hand)

First time in a repo with `docs/superpowers/` or fr config: **never**
manually create, move, or archive files under it (#378). Run in order —
`fr status`/`fr repair`/`fr migrate v1-to-v2` preview by default, no `--yes`:

```bash
fr --help                       # confirm fr is installed / repo is fr-managed
fr status                       # repo-wide sweep: archivable + in-progress plans
fr acceptance check             # matrix gate; exit 2 on failing rows
fr repair                       # preview stale-ref rewrites
ls docs/superpowers/plans/*.md 2>/dev/null   # hits = legacy v1 plans (v2 is folders)
fr migrate v1-to-v2             # if the ls above found hits
fr spec status --all            # per-spec rollup before deciding what's "done"
fr archive --all                # only now, for plans the sweep marked archivable
```

`.md.v1-archive` files (from `fr migrate v1-to-v2`) are pre-migration
originals kept for git-history — leave them; `fr archive` only moves
the plan folder, not the `.v1-archive` sibling (a known gap).

## How it works (no separate state store)

`vk` is a single state machine: the plan files (`_meta.yaml` + `NN.yaml`) are
the source of truth, and every projection (Issue body / labels / state, spec
table row) is computed on demand. There's nothing to "sync" — `fr apply`
diffs the projection against observed gh state and emits the mutations
needed to bring them in line.

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
plans resolve via the gh contents API (same capability `fr archive` uses);
pass `--no-gh` (or run offline) and cross-repo rows degrade to
`Unreachable`. `.github/workflows/fr-spec-status.yml` posts this as a PR
comment when a PR touching `docs/superpowers/{plans,implemented/plans}/` merges.

For a single plan, `fr status <plan-dir>` is the read-only deep report:
header, per-phase table, completion-guard refusals, drift warnings, and the
archive nudge. Safe to allowlist — it never mutates.

## Acceptance debt

`fr acceptance status` — counts by status + open `skipped` /
`not-implemented` rows (backfill owed, oldest first); `--brief` is the capped
session-start form. `fr status <plan-dir>` appends the same summary when the
repo has `docs/acceptance/matrix.yaml`. See `fr-acceptance` for backfill.

## Tick / complete phases

```bash
fr plan edit <plan-dir> --tick P<n>.T<n>.S<n> --state x
fr plan edit <plan-dir> --tick P<n>.T<n>.S<n> --state - --note "<reason>"
fr plan edit <plan-dir> --complete-phase N
fr plan edit <plan-dir> --complete-phase N --note "ran <runbook ref>"  # required for manual phases
```

`--tick` is idempotent; `--complete-phase` refuses agentic phases with
unticked steps (use rework for deferred items — see `fr-plan`).

## Archive-on-complete

When a plan is finished, archive it with the verb, never a hand-rolled mv:

```bash
fr archive <plan-dir>     # gate-checked git mv to docs/superpowers/implemented/plans/
fr archive --all          # sweep every finished plan; specs follow when all their rows are implemented
```

The gate requires every phase complete (gh evidence, or fully-ticked
never-dispatched); `--force` overrides for a single plan. The owning spec
moves to `implemented/specs/` once all its rows resolve as implemented; the
operator still runs the command and commits — archiving never fires without
intent (the v1 footgun), it's one verb, not a manual mv.

Rows reported Unreachable/Missing mean stale refs — normalize with
`fr repair --yes` (see preflight above). Legacy `archived-plans/` layouts
hard-stop every verb until `fr migrate dirs --yes` runs.
