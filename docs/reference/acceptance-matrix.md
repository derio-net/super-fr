---
title: "The acceptance matrix"
tldr: |
  One row per thing an operator should be able to do, each with the tests that prove it and an honest status. The commands that keep it true and the statuses that mean debt.
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/acceptance/**
  - packages/fr/src/fr/commands/acceptance_cmd.py
reviewed: 2026-11-12 acceptance-fragments phase 4 documents report, pages-check and comment; reports are derived and `check` fails on a tracked one
---

# The acceptance matrix

Passing unit tests do not tell you whether the product does what you promised. The
acceptance matrix does: one row per business-level promise ("an operator can X"), the
tests at each level that verify it, and a status that says how much you can trust it. The
skill that drives it is [fr-acceptance](../explainers/fr-acceptance.md).

## Where the rows live

Each row belongs to the feature that created it, and lives in that feature's
**fragment**, `docs/acceptance/features/<spec-slug>.yaml`. A fragment names its feature
(the file stem), the repo (`repo: <org>/<repo>`) and its rows; `legacy.yaml` holds the
rows that cite no single spec, such as those born from a debug journal. The matrix you
read is never stored: fr **folds** every fragment, in the order the default branch's
history introduced them, and every reader (`check`, `status`, `fr debt`, plan
self-review, the PR body, close-out) reads that fold. Two features editing their own
fragments no longer touch the same file.

Rows cite fr's own artifacts **logically**: `spec:<slug>#R<n>` for a spec requirement,
`plan:<slug>` for a plan. The slug is the spec's file name without `-design.md`, so it is
the same before and after `fr archive` moves the spec, and an archive never rewrites a
row. Code keeps its path form, `<repo>:<path>#<test>`.

A repo that still has the single `docs/acceptance/matrix.yaml` of earlier fr versions is
migrated by `fr migrate artifacts --yes`: the rows are split by origin spec, path
references to specs and plans become logical, and the matrix and its committed reports
are deleted.

A branch that was still editing `matrix.yaml` when its base split it keeps the file
through `git merge`. The next fr command splits it again, carrying over only what the
fragments lack. A row they do not know goes to its spec's fragment, and a row they hold
identically is dropped. A row they hold *differently* stops the migration, which names
the row and leaves every file as it was. Put that row back as the fragments hold it, or
delete it from `matrix.yaml`, run `fr migrate artifacts --yes`, and then re-apply your
change with `fr acceptance set-status`.

A repo can turn the matrix off with `artifacts.acceptance: off` in `.fr/settings.yaml`
(`fr settings show`). fr then writes no rows, reports or matrix CI. `fr acceptance add` and
`set-status` refuse, naming the setting. `check`, `status`, `fr debt` and the session-start
nag say "disabled by repo setting" instead of reporting debt.

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
`acceptance:` list, and moved up the ladder as phases complete
(`fr plan edit --complete-phase` warns about a phase that completes without moving its
rows). A row added mid-flight is allowed and visible: `fr acceptance check --added-since <ref>`
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

Never edit a fragment by hand: `add` and `set-status` validate the row and commit only the
fragment they changed. A row whose origins name no single spec needs `--feature <slug>`
(`legacy` for none). Test references are anchored on a test's name, for example
`repo:tests/unit/test_x.py#test_y`, never a line number, because a line number slides onto
whatever test lands there next.

Reports are never committed. The scaffolded CI shows the report as a job summary (GitHub,
Gitea) or an exposed artifact (GitLab), and publishes the HTML on Pages only when
`fr acceptance pages-check` proves the site no wider than the repo; the Pages job re-checks
before every deploy.

The per-PR gate is `.github/workflows/acceptance-report.yml`, which on a weekly
schedule also runs `fr debt issue`, keeping one "Technical debt" issue up to date (its
Acceptance section lists the rows still owed). Rows can additionally name a verification strategy and a
walk scenario; that is covered in the [verification strategies guide](../verification-strategies.md).
