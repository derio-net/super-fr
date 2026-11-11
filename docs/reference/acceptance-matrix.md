---
title: "The acceptance matrix"
tldr: |
  One row per thing an operator should be able to do, each with the tests that prove it and an honest status. The commands that keep it true and the statuses that mean debt.
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/acceptance/**
  - packages/fr/src/fr/commands/acceptance_cmd.py
  - docs/acceptance/matrix.yaml
reviewed: 2026-11-11 docs-currency phase 5
---

# The acceptance matrix

Passing unit tests do not tell you whether the product does what you promised. The
acceptance matrix, `docs/acceptance/matrix.yaml`, does: one row per business-level promise
("an operator can X"), the tests at each level that verify it, and a status that says how
much you can trust it. The skill that drives it is [fr-acceptance](../explainers/fr-acceptance.md).

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
fr acceptance init                   # scaffold the matrix, the backfill rule and (with CI present) the workflow
fr acceptance backfill               # print an inventory and the protocol for an existing repo
fr acceptance add --id ... --capability ... --acceptance ... --status ...   # append a row
fr acceptance set-status --id ... --status ... --notes "why"                 # move a row, with a reason
fr acceptance check                  # refs, staleness, statuses; exit 2 on any failing row
fr acceptance status                 # the open debt, briefly (a session-start hook shows it)
fr acceptance report --deterministic # re-render the committed reports
```

Never edit the YAML by hand: `add` and `set-status` validate the row and regenerate the
three committed reports (two HTML, one Markdown). Test references are anchored on a test's
name, for example `repo:tests/unit/test_x.py#test_y`, never a line number, because a line
number slides onto whatever test lands there next.

The per-PR gate is `.github/workflows/acceptance-report.yml`, which on a weekly
schedule also runs `fr debt issue`, keeping one "Technical debt" issue up to date (its
Acceptance section lists the rows still owed). Rows can additionally name a verification strategy and a
walk scenario; that is covered in the [verification strategies guide](../verification-strategies.md).
