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
fr status                       # repo-wide sweep: four buckets, judged against origin/<default>
fr acceptance check             # matrix gate; exit 2 on failing rows
fr repair                       # preview stale-ref rewrites
ls docs/superpowers/plans/*.md 2>/dev/null || true   # hits = legacy v1 plans (v2 is folders)
fr migrate v1-to-v2             # if the ls above found hits
fr spec status --all            # per-spec rollup before deciding what's "done"
fr archive docs/superpowers/plans/<name>   # only now, one per plan the sweep printed it for
```

The sweep fetches, then calls a plan merged only when every agentic phase is
complete on `origin/<default>`; local ticks never count. Buckets: **merged but
not archived** (each with its own `fr archive <plan-dir>` line: run those, one
per plan, never `--all`), **merged, manual phases still open** (tick them
first), **complete locally, not yet on origin/<default>** (waiting for merge,
no command), **in progress**. `merge state unknown` = no remote-tracking
default ref (try `git fetch` / `git remote set-head origin -a`).

`.md.v1-archive` files (from `fr migrate v1-to-v2`) are pre-migration originals
kept for git-history; leave them (`fr archive` does not move them, a known gap).

## How it works (no separate state store)

The plan files (`_meta.yaml` + `NN.yaml`) are the source of truth; every
projection (Issue body / labels / state, spec row) is computed on demand, and
`fr apply` diffs it against observed gh state. There is nothing to "sync".

## Audit drift on a plan

```bash
fr apply <plan-dir>             # default: dry-run; prints what would change
fr apply <plan-dir> --yes       # apply the changes
fr apply --all                  # walk every plan in docs/superpowers/plans/
fr apply <plan-dir> --format json   # machine-readable; empty diff = in sync
```

## Spec rollup

```bash
fr spec status <spec-path>      # one spec
fr spec status --all            # every spec in docs/superpowers/specs/
```

Output is markdown: per-plan state (Not Started / In Progress / Complete /
Missing / Unreachable), step + phase counts, and an aggregate. Cross-repo
plans resolve via the gh contents API; with `--no-gh` (or offline) they
degrade to `Unreachable`. `.github/workflows/fr-spec-status.yml` posts this
as a PR comment when a PR touching plans merges.

`fr status <plan-dir>` is the read-only single-plan report: per-phase table,
completion-guard refusals, drift warnings, archive nudge. Safe to allowlist:
it never mutates the repo or gh (it may `git fetch` remote-tracking refs).

## Acceptance debt

`fr acceptance status` — counts by status + open `skipped` / `not-implemented`
rows (oldest first); `--brief` is the session-start form. `fr status <plan-dir>`
appends the same summary when a matrix exists. See `fr-acceptance`.

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

When a plan is finished **and merged** (`fr status` lists it as merged but not
archived), archive it with the verb it printed, never a hand-rolled mv:

```bash
fr archive <plan-dir>     # gate-checked git mv to docs/superpowers/implemented/plans/
```

The gate requires every phase complete (gh evidence, or fully-ticked
never-dispatched); `--force` overrides for a single plan. The owning spec
moves to `implemented/specs/` once all its rows resolve as implemented. The
moves are staged `git mv`s: you commit them. Never fires without intent.

Rows reported Unreachable/Missing mean stale refs — normalize with
`fr repair --yes` (see preflight above). Legacy `archived-plans/` layouts
hard-stop every verb until `fr migrate dirs --yes` runs.
