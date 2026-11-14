---
title: "The acceptance matrix"
tldr: |
  One row per thing an operator should be able to do, each with the tests that prove it and an honest status. The commands that keep it true and the statuses that mean debt.
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/acceptance/**
  - packages/fr/src/fr/commands/acceptance_cmd.py
reviewed: 2026-11-14 quiet/stealth plans, deliver and close-out read artifacts where they live (debug 2026-11-13-placement-plan-paths)
---

# The acceptance matrix

Unit tests that pass do not tell you if the product does what you promised. The
acceptance matrix tells you. It has one row for each business-level promise ("an operator
can X"), the tests at each level that prove it, and a status. The status tells you how much
you can trust the row. The skill that drives it is [fr-acceptance](../explainers/fr-acceptance.md).

## Where the rows live

Each row belongs to the feature that created it. The row lives in that feature's
**fragment**, `docs/acceptance/features/<spec-slug>.yaml`. A fragment names its feature
(the file stem), the repo (`repo: <org>/<repo>`) and its rows. `legacy.yaml` holds the
rows that cite no single spec, such as those born from a debug journal.

The matrix you read is never stored. fr **folds** every fragment, in the order that the
default branch's history added them. Every reader (`check`, `status`, `fr debt`, plan
self-review, the PR body, close-out) reads that fold. Two features that edit their own
fragments no longer touch the same file.

Under the quiet and stealth placements, the default branch holds no fragment. Each
feature's fragments sit in its own feature path. A feature counts as merged when its code
branch merged. The proof is a head of its own on the default branch, past the `BASE` that
it claimed its path from. For a squash or rebase merge, the proof is the forge's merged pull
request.

The amendments of a merged feature apply in the order of the default branch's first-parent
commit that merged it. They are read as they were pushed at that merge. A feature that is
not merged yet adds its own amendments only to its own branch's view. An amendment that the
feature writes after its merge is pending on its branch. `fr
acceptance check` does not accept an in-place edit of its merged row.

`fr acceptance status` lists the merged features in that order, and the unmerged ones with
the reason why. A row that another merged feature created changes only by an amendment in
your feature's fragment (`fr acceptance amend`, or `set-status`, which writes one).

A row that is still pending on your branch has no history yet. Thus you can correct a
mistyped origin in place with `fr acceptance amend --id <row> --op reword --origin
spec:<slug>#R<n> --why "<reason>"`. This command rewrites the row. If the corrected origin
names another spec, the command also moves the row to the fragment of that spec. The
origins of a merged row are history: for such a row, `--origin` stops with an error.

Rows cite fr's own artifacts **logically**: `spec:<slug>#R<n>` for a spec requirement,
`plan:<slug>` for a plan. The slug is the spec's file name without `-design.md`. So the
slug is the same before and after `fr archive` moves the spec, and an archive never
rewrites a row. Code keeps its path form, `<repo>:<path>#<test>`.

`fr migrate artifacts --yes` migrates a repo that still has the single
`docs/acceptance/matrix.yaml` of earlier fr versions. It splits the rows by origin spec,
and it makes the path references to specs and plans logical. Then it deletes the matrix and
its committed reports.

A branch that still edited `matrix.yaml` when its base split it keeps the file through
`git merge`. The next fr command splits it again, and carries over only what the fragments
do not have. A row that the fragments do not know goes to its spec's fragment. A row that
they hold identically is dropped. A row that they hold *differently* stops the migration.
The migration names the row and leaves every file as it was.

To continue, put that row back as the fragments hold it, or delete it from `matrix.yaml`.
Then run `fr migrate artifacts --yes`, and then apply your change again with
`fr acceptance set-status`.

A repo can turn the matrix off with `artifacts.acceptance: off` in `.fr/settings.yaml`
(`fr settings show`). fr then writes no rows, reports or matrix CI. `fr acceptance add` and
`set-status` stop and name the setting. `check`, `status`, `fr debt` and the session-start
nag say "disabled by repo setting" and report no debt.

## Statuses

| Status | Meaning |
|---|---|
| `ci`, `scheduled` | Automated, so it cannot quietly drift. |
| `walked` | Proven live; dated by its latest passing walk. |
| `manual` | A process that will never be automated. Listed, not debt. |
| `unwired` | A test exists but CI does not run it. Debt. |
| `walk-owed` | A live or post-merge walk is still owed. Debt. |
| `not-implemented` | Nothing exists yet. Debt. |
| `failing` | Known red. Fails CI on purpose until fixed or reclassified with a reason. |

## How rows are born and move

Rows are proposed at brainstorm time, linked to plan phases through each phase's
`acceptance:` list, and moved up the ladder as phases complete.
`fr plan edit --complete-phase` warns about a phase that completes but does not move its
rows. A row added mid-flight is allowed and visible: `fr acceptance check --added-since <ref>`
lists it, and the PR body defends it.

## Commands

```bash
fr acceptance init                   # scaffold docs/acceptance/features/, the backfill rule and (with CI present) the workflow
fr acceptance backfill               # print an inventory and the protocol for an existing repo
fr acceptance add --id ... --capability ... --acceptance ... --origin spec:<slug>#R1 --status ...   # a row, in its spec's fragment
fr acceptance set-status --id ... --status ... --notes "why"                 # move a row, with a reason
fr acceptance check                  # refs, staleness, statuses; exit 2 on any failing row
fr acceptance status                 # the open debt, briefly (a session-start hook shows it)
fr acceptance report [--open]        # render the derived report locally (git-ignored, never committed; --format md)
fr acceptance pages-check            # exit 0 only if a Pages site would be no wider than the repo (fails closed)
fr acceptance comment --pr N --yes   # keep one PR comment with the Markdown report (forge.report_comment: on)
```

Never edit a fragment by hand. `add` and `set-status` validate the row and commit only the
fragment that they changed. A row whose origins name no single spec needs `--feature <slug>`
(`legacy` for none). Test references are anchored on the name of a test, for example
`repo:tests/unit/test_x.py#test_y`, never on a line number. A line number slides onto
whatever test lands there next.

Reports are never committed. The scaffolded CI shows the report as a job summary (GitHub,
Gitea) or an exposed artifact (GitLab). It publishes the HTML on Pages only when
`fr acceptance pages-check` proves that the site is no wider than the repo. The Pages job
checks again before every deploy.

The per-PR gate is `.github/workflows/acceptance-report.yml`. On a weekly schedule, it also
runs `fr debt issue`, which keeps one "Technical debt" issue up to date. Its Acceptance
section lists the rows still owed. Rows can also name a verification strategy and a walk
scenario. The [verification strategies guide](../verification-strategies.md) covers them.
