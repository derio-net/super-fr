---
title: "fr-triage: Ranking a Backlog, and Learning Where Defects Come From"
date: 2026-11-11
draft: false
tldr: |
  A backlog is a pile until someone judges it. fr-triage keeps those judgements in a
  file the engine reads and writes around, so a re-run costs only what is new, and a
  group of related issues can be shipped as one reviewed pull request. fr-origins
  asks the sibling question: where did the recent bugs come from?
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-triage/SKILL.md
  - plugins/super-fr/skills/fr-origins/SKILL.md
  - packages/fr/src/fr/triage/**
  - packages/fr/src/fr/commands/triage_cmd.py
  - packages/fr/src/fr/commands/triage_batch_cmd.py
  - packages/fr/src/fr/commands/triage_origins_cmd.py
reviewed: 2026-11-12 placement-resolver phase 2, artifact directories now come from fr.artifacts.paths; the paths and behaviour this page describes are unchanged
---

## Overview: judgement in a file, engine around it

Triage is two jobs. One is mechanical: fetch the issues, notice what changed, draw the
page. The other needs judgement: which issue costs most if ignored, which two are the same
bug, which five belong in one change. fr splits them cleanly. The **engine**, `fr triage`,
does the mechanical job and is the same on every harness. The **skill** holds only the
discipline for the judging, and your judgements are written to a file the engine reads.

The consequence is cheap sync. A second triage is the same loop, and `check` names only
what arrived, shipped or went missing since your last pass, so nothing is re-judged.

You reach for it when you are asked to triage, rank or organise the open issues of a repo
or a whole organisation, want a board of "what next", or want to refresh a triage you did
before. You reach for **fr-origins** when the question is where recent bugs came from and
which process change would have prevented them.

## A worked example

```bash
fr triage collect --repo example-org/example-repo
fr triage check   --repo example-org/example-repo
```

`collect` reads the forge and writes `facts.json`. `check` prints the sets you act on. The
important one is **unranked**: open issues with no judgement yet. You read each one and the
code it names, then add an entry to `judgements.yaml`. It sits beside `facts.json` in the
scope's state directory (`.fr/triage-state/example-org--example-repo/` in a clone; `collect`
prints the path), and you create it on the first run:

```yaml
schema: 12
ranked_at: 2026-11-11
tiers:
  - {n: 1, title: "Data loss", description: "Work destroyed with no prompt or salvage."}
issues:
  "example-repo#435":
    tier: 1
    theme: isolation
    severity: high
    cx: S
    verified: true
    detail: "`gc()` trusts the merged state and tears down locally. Still live on main."
```

`tier` is the priority group, `severity` is `low`, `med` or `high` (`check` lists a judged
issue that has none), and `cx` is your size estimate of the fix: `XS`, `S`, `S-M`, `M` or `L`.

Then draw the page:

```bash
fr triage render --repo example-org/example-repo --open
```

You get `triage.html`: what changed since the last report, what needs you right now, the
driver's order for what is next, and the backlog by tier. When several judged issues share a
subsystem, propose them as a batch:

```bash
fr triage batch create merged-trust --repo example-org/example-repo --title "Stop trusting merged state" \
    --issue "example-repo#435" --issue "example-repo#469"
```

## State: three files, three owners

Everything lives in the scope's state directory: `.fr/triage-state/<scope>/` in a clone,
`~/.cache/fr/triage/<scope>/` outside one. A scope is `owner--repo` for `--repo`, or the
owner for `--org`; `--repo A/B,C/D` is a group.

| File | Written by | Holds |
|---|---|---|
| `facts.json` | `fr triage collect` | forge data: issues, labels, PRs |
| `judgements.yaml` | **you**, plus the `batch` verbs | tiers, rankings, kinds, patterns, batches |
| `triage.html`, `board.html` | `render`, `board` | the pages |

Never write the facts yourself. State is not committed; its durable copy is an orphan
branch, `refs/heads/fr-triage/<scope-id>`, which fr fetches before reading and pushes after
every change. `fr triage state export --to <dir>` and `import --from <dir>` copy it to and
from a repo.

## What `check` tells you

It always exits 0 and prints sets, not verdicts:

- **unranked**, issues and PRs: your work queue;
- **settled**: judged, now closed. Report what shipped and keep the judgement;
- **orphaned**: the key names a repo collect did not read, a typo or a rename. The only
  set safe to act on without the forge;
- **unreachable**: collect could not settle it (rate limit, lost access). Never prune on
  this;
- **stale dispatch**, **awaiting live**, **unplaced**, **duplicate candidates**: batches
  that went quiet, issues waiting on a post-merge walk, issues in no batch, and pairs the
  engine proposes as duplicates. A proposal is not a verdict: you judge every group.

Open pull requests are triaged in the same loop. Each carries an intent anchor, the thing
that says what the PR is for (the issue it closes, a spec, a debug journal, or none), and you mark it `delivers`, `partial`, `drift` or
`unanchored` with one line. It is shallow by design: never a code review.

## How to judge

1. **Tier by what the failure costs**: lost work first, then a failure that looks like
   success, then friction. Never by age, label, reporter or how loud the issue is.
2. **Verify against current main.** Before `verified: true`, re-read the cited line. At forty
   issues a fixed bug stays ranked as live. If you did not re-read it, write
   `verified: false`.
3. **Record line drift** in `detail`. A bug already fixed is a close recommendation, not a
   ranking.
4. **Hunt duplicates and batches.** Record a duplicate in `duplicate_of` (or `distinct_from`
   for a pair that only looks alike), never as prose. Three or more issues with one root
   cause become a `patterns` entry.
5. **Forge actions are unrun commands.** A close, a dedupe or a relabel is the exact command
   in your report, for the operator to run. Never act on the forge unasked.

Quote every title and note in the YAML: an unquoted `: ` breaks the file.

## Batches and the driver

A **batch** is a group of judged issues delivered as one [fr-goal](01-fr-goal.md) run and
one pull request. The `fr triage batch` verbs are `list`, `create`, `edit`, `cancel`,
`suggest` (candidate groupings; input, never the answer), `dispatch`, `adopt`, `merge`,
`closeout`, `drive`, `replace` and `focus`. `dispatch`, `merge` and `cancel` write to the
forge only with `--yes`; without it they print the plan.

`fr triage batch drive` runs batches to completion in waves. A wave is a set of batches that
may run at the same time; a batch names the wave it belongs to, or the batch it must come
`after`. The driver merges ready pull requests one after another in a fixed order (a merge
train), closes out what has landed, and dispatches what may start. Merging a batch
pull request needs the operator's `approved-fr` label. The driver never approves its own
work. `fr triage board` draws `board.html`, a Kanban of every batch by lifecycle column, with
four "Needs you" lanes (developer, reviewer, tester, devops) decided from the run's cursor
and the merged PR's gate labels, never from a session's status. On a wide screen a column
with no cards folds to a narrow strip with its title turned on its side, so the columns that
hold cards get the room.

Several scopes can work one repo, so a scope **claims** each issue it plans to act on with an
`fr:claimed` label and a marker comment. Another scope's claim is hands-off. Taking one over
(`fr triage claim take`) or releasing it is the operator's call, never yours. Runners, restarts
and the cloud driver are covered in the [herdr guide](../herdr-control-sessions.md) and the
[cloud guide](../cloud-setup.md). [The wave driver](fr-wave-driver.md) walks through what one pass does and where you act.

## fr-origins: where did the bugs come from?

You can read an issue and the code it names. A classification done in chat dies with the
session; `fr triage origins` keeps it, so a re-run costs only what arrived.

```bash
fr triage origins collect --repo example-org/example-repo --since 2026-10-01
fr triage origins check   --repo example-org/example-repo
fr triage origins render  --repo example-org/example-repo
```

`collect` writes `origins-facts.json`; you write `origins.yaml`, one classification per
issue; `render` builds `origins.html`. A window wider than one page is refused, naming a
`--since` it does cover. The categories describe what the defect *is*, not who noticed it:

- **latent**: always there, nothing changed it;
- **regression**: a change broke something that worked, and you can name the pull request;
- **new-feature**: a defect in something recently added;
- **leftover**: work a PR should have finished and did not;
- **gap**: a missing capability or test nobody claimed;
- **duplicate**: the same defect as another issue; name it.

Each entry also carries a source (`pipeline`, `recording` or `hand`) and a severity. A
regression with no `pr:` is invalid, and one bad entry makes every verb that reads the file
exit 2. Read the body and the code; a title is a hypothesis. The page ends with `causes:`,
each linked to the batch that addresses it and a one-line process change.

## Limits

- The engine ranks nothing. Every tier is your judgement.
- `check` is as current as the last `collect`.
- Pages are rewritten on each render; hand-written analysis goes in the fragments listed in
  each page's `manifest.yaml`, never in an edited page.
- Keep state and pages local for any repo that is not yours. A privacy guard refuses to
  batch a private repo's issue into a scope whose state repo is public.

## Where to go next

- [fr-goal](01-fr-goal.md) is the run a batch becomes.
- [fr-audit](fr-audit.md) draws the architecture page and the cost of a run.
- [fr-acceptance](fr-acceptance.md) covers the post-merge walks that keep an issue open.
