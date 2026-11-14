---
title: "fr-progress: Where Does This Plan Stand?"
date: 2026-11-11
draft: false
tldr: |
  A plan is a folder of facts, so "how far along is it" is a computed answer, not
  something to keep in sync. fr-progress is the set of read-mostly commands that
  compute it, plus the checks to run before you touch the planning tree by hand.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-progress/SKILL.md
  - packages/fr/src/fr/commands/status_cmd.py
  - packages/fr/src/fr/commands/spec_cmd.py
  - packages/fr/src/fr/commands/archive_cmd.py
  - packages/fr/src/fr/commands/repair_cmd.py
reviewed: 2026-11-12 placement-resolver phase 2, artifact directories now come from fr.artifacts.paths; the paths and behaviour this page describes are unchanged
---

## Why is there nothing to sync?

Most trackers keep a second copy of the truth and then spend effort reconciling it with
the first. fr does not. A plan's `_meta.yaml` and per-phase `NN.yaml` files are the
source of truth, and fr computes every projection (a GitHub issue's body, its labels and
state, a row in the spec's plan table) on demand. When you want to know where things
stand, a command reads the files and, where relevant, the forge, and tells you.

You reach for these commands to answer "what is in progress", "is this plan done and
merged", "has GitHub drifted from the plan", and to clean up once work has shipped.

## What does a worked example look like?

You return to a repo after a week and want to know what is going on:

```bash
fr status
```

With no argument it fetches, then sorts every plan into four buckets, judged against the
default branch on the remote:

- **merged but not archived**, each listed with the exact `fr archive` line to run;
- **merged with manual phases still open**;
- **complete locally but not yet on the default branch**;
- **in progress**.

A plan counts as merged only
when every agentic phase is complete *on the default branch*. Ticks that exist only on
your machine never count. If you see `merge state unknown`, there is no remote-tracking
default ref: try `git fetch` or `git remote set-head origin -a`.

One plan in more detail:

```bash
fr status docs/superpowers/plans/<slug>
```

That prints a per-phase table, any completion-guard refusals, drift warnings and an
archive nudge. It never mutates anything, though it may update remote-tracking refs with
a fetch.

## Which commands are there?

| You want | Run |
|---|---|
| Every plan, bucketed | `fr status` |
| One plan's detail | `fr status <plan-dir>` |
| One spec's rollup | `fr spec status <spec-path>` |
| Every spec's rollup | `fr spec status --all` |
| What GitHub would change | `fr apply <plan-dir>` (dry run) |
| Mark a step done | `fr plan edit <plan-dir> --tick P<n>.T<n>.S<n>` |
| Mark a phase done | `fr plan edit <plan-dir> --complete-phase N` |
| Acceptance debt | `fr acceptance status` |

`fr spec status` prints Markdown: per-plan state (Not Started, In Progress, Complete,
Missing or Unreachable), step and phase counts and a total. Plans in another repo resolve
through the GitHub contents API; `--no-gh` keeps it local, and those rows then read
`Unreachable`. The repo's `fr-spec-status.yml` workflow posts the same output as a
comment when a pull request touching plans merges.

`fr apply` is where drift shows. Without `--yes` it only previews what it would change on
GitHub; with `--yes` it applies; `--all` walks every plan and `--format json` is the
machine form, where an empty diff means in sync. It is safe to run repeatedly.

`--tick` is idempotent. `--complete-phase` refuses an agentic phase that still has
unticked steps, and a manual phase needs `--note` saying what was done.

## What do you run before you touch `docs/superpowers/` by hand?

Do not create, move or archive files under it yourself. In a repo you have not worked in,
run this in order (`status` only reads and takes no `--yes`; `repair` and `migrate`
preview unless you pass `--yes`):

```bash
fr --help                 # fr is installed, and the repo is fr-managed
fr status                 # the repo-wide sweep above
fr acceptance check       # the matrix gate; exit 2 on failing rows
fr repair                 # preview stale-reference rewrites
fr migrate v1-to-v2       # only if plans/*.md files exist (legacy v1 plans)
fr spec status --all      # per-spec rollup, before deciding what is done
```

`fr repair --yes` normalises stale plan and spec references and strips dead config keys.
A legacy `archived-plans/` layout stops every verb until `fr migrate dirs --yes` runs.
The `.md.v1-archive` files a migration leaves behind are pre-migration originals kept for
history; leave them.

## How do you archive finished work?

When `fr status` lists a plan as merged but not archived, use the verb it printed:

```bash
fr archive docs/superpowers/plans/<name>
```

The move is a gate-checked `git mv` into `docs/superpowers/implemented/plans/`. The gate
wants every phase complete: a dispatched phase by evidence on GitHub, an agentic one
fully ticked and on the default branch, a manual one ticked locally. `--force` overrides
for one plan. The owning spec follows once every plan in its Implementation Plans table has reached the
archive.

fr stages the moves and does not commit them, so you commit them. `--branch <merged-branch>`
archives everything that branch added, and prints `held:` for anything not yet ready. The
archive leaves acceptance rows alone: they cite a spec as `spec:<slug>`, which names it in
either place.

## What can these commands not tell you?

- `fr status` is only as current as your last fetch.
- Progress here means *plan steps*. Whether the behaviour works is the acceptance
  matrix's job: see [fr-acceptance](fr-acceptance.md).
- Archived plans are history, and they stay as they are. No command rewrites them.

## Where do you go next?

- [fr-brainstorming-and-plan](fr-brainstorming-and-plan.md) explains the plan folder you
  are querying.
- [fr-dispatch](fr-dispatch.md) covers the GitHub side `fr apply` reconciles.
