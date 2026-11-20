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
reviewed: 2026-11-20 wave-merge-queue phase 5 fixes, the merge train is gone (one queue per repo; a repo with no queue block merges nothing); wave-merge-queue phase 1 fixes, a moved identical change counts as the same diff; wave-merge-queue phase 1, judgements schema 13 and an approval pinned to the pull request's diff; 2026-11-19 batch docs-wording changes help text and docstrings only (bracketed help renders, first lines shortened for STE, `fr ops gate` hint names the full scaffold command); still true; 2026-11-17 the untrusted set of check, and the intake rule (batch triage-intake, facts schema 15 on top of main's 14); collect only reads the forge (it reports repos without approved-fr, and the first dispatch creates the label); scope retire settles closed issues. 2026-11-15 still true, the gate ledger now also reads archived run cursors (batch gate-truth); 2026-11-19 a full PR list warns (may show not collected); Batches columns fold and the wave cutoff; Origins groups, state filter and merged PRs. 2026-11-18 one name per page (fr triage backlog writes backlog.html and issues.html, fr triage batches writes batches.html; render and board stay as aliases). 2026-11-17 the untrusted set of check, and the intake rule (batch triage-intake, facts schema 15 on top of main's 14); collect only reads the forge (it reports repos without approved-fr, and the first dispatch creates the label); scope retire settles closed issues. 2026-11-15 still true, the gate ledger now also reads archived run cursors (batch gate-truth)
---

## Why keep the judgement in a file, with an engine around it?

Triage is two jobs. One is mechanical: fetch the issues, notice what changed, draw the
page. The other needs judgement: which issue costs most if ignored, which two are the same
bug, which five belong in one change. fr splits them cleanly. The **engine**, `fr triage`,
does the mechanical job and is the same on every harness. The **skill** holds only the
discipline for the judging, and you write your judgements to a file the engine reads.

The consequence is cheap sync. A second triage is the same loop, and `check` names only
what arrived, shipped or went missing since your last pass, so nothing is re-judged.

You reach for it when someone asks you to triage, rank or organise the open issues of a
repo or a whole organisation. You also reach for it to get a board of "what next", or to
refresh a triage you did before. You reach for **fr-origins** when the question is where recent bugs came from and
which process change would have prevented them.

## What does a worked example look like?

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

Then draw the pages:

```bash
fr triage backlog --repo example-org/example-repo --open
```

You get two pages. `backlog.html` holds the decisions: what changed since the last report,
what needs you right now, the driver's order for what is next, the waves and the batches.
`issues.html` holds the lists: the backlog by tier, ranked features, parked issues, debt and
open pull requests. (`fr triage render` is the old name of this command and still works.) When several judged issues share a
subsystem, propose them as a batch:

```bash
fr triage batch create merged-trust --repo example-org/example-repo --title "Stop trusting merged state" \
    --issue "example-repo#435" --issue "example-repo#469"
```

## Which files hold the state, and who writes them?

Everything lives in the scope's state directory: `.fr/triage-state/<scope>/` in a clone,
`~/.cache/fr/triage/<scope>/` outside one. A scope is `owner--repo` for `--repo`, or the
owner for `--org`; `--repo A/B,C/D` is a group.

| File | Written by | Holds |
|---|---|---|
| `facts.json` | `fr triage collect` | forge data: issues, labels, PRs (it only reads the forge) |
| `judgements.yaml` | **you**, plus the `batch` verbs | tiers, rankings, kinds, patterns, batches |
| `backlog.html`, `issues.html`, `batches.html` | `backlog`, `batches` | the pages |

Never write the facts yourself. fr does not commit the state by default; its durable copy
is an orphan branch, `refs/heads/fr-triage/<scope-id>`, which fr fetches before reading and pushes after
every change. `fr triage state export --to <dir>` and `import --from <dir>` copy it to and
from a repo.

## What does `check` tell you?

It always exits 0 and prints sets, not verdicts:

- **unranked**, issues and PRs: your work queue;
- **settled**: judged, now closed. Report what shipped and keep the judgement;
- **orphaned**: the key names a repo collect did not read, a typo or a rename. The only
  set safe to act on without the forge;
- **unreachable**: collect could not settle it (rate limit, lost access). Never prune on
  this;
- **untrusted**: open issues whose author is an outside account that no operator admitted,
  each with its reason. Collect does not store their body. You never judge, rank or batch
  one. An operator admits one with the `ready-fr` label;
- **stale dispatch**, **awaiting live**, **unplaced**, **duplicate candidates**: batches
  that went quiet, issues waiting on a post-merge walk, issues in no batch, and pairs the
  engine proposes as duplicates. A proposal is not a verdict: you judge every group.

You triage open pull requests in the same loop. Each carries an intent anchor, the thing
that says what the PR is for: the issue it closes, a spec, a debug journal, or none. You mark
it `delivers`, `partial`, `drift` or `unanchored` with one line. It is shallow by design: never a code review.

## How do you judge?

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

## What are batches and the driver?

A **batch** is a group of judged issues delivered as one [fr-goal](01-fr-goal.md) run (an
fr-debugging run for a batch created or edited with `--skill debug`) and one pull request. The `fr triage batch` verbs are `list`, `create`, `edit`, `cancel`,
`suggest` (candidate groupings; input, never the answer), `dispatch`, `adopt`, `merge`,
`closeout`, `drive`, `replace` and `focus`. `dispatch`, `merge` and `cancel` write to the
forge only with `--yes`; without it they print the plan.

`fr triage batch drive` runs batches to completion in waves. A wave is a set of batches that
may run at the same time; a batch names the wave it belongs to, or the batch it must come
`after`. The driver merges ready pull requests through one merge queue per repo: it tests each
ready pull request on top of the ones ahead of it, in the order they became ready, and lands
the tested result. A repo needs a `queue:` block in `.fr/triage.yaml`; without one the driver
holds every merge and says so under Needs you now. The driver also closes out what has landed
and dispatches what may start. Merging a batch pull request needs the operator's `approved-fr`
label, which holds while the pull request's own diff stays the same. A block of changes moved
unchanged to another place in the same file counts as the same diff. The driver never writes
to a pull request's branch and never approves its own work.

`fr triage batches` draws `batches.html`, a Kanban of every batch by lifecycle column. It has
four "Needs you" lanes (developer, reviewer, tester, devops), which the board decides from
the run's cursor and the merged PR's gate labels, never from a session's status. Every column
has a button in its header that folds it and opens it again. A column with no cards starts
folded, and on a wide screen a folded column is a narrow strip with its title turned on its
side, so the columns that hold cards get the room. The page remembers each column in your
browser, so the automatic reload keeps what you chose. A toggle, "last 30 days" by default,
hides every wave whose batches are all finished and have had no event in the last 30 days;
"all waves" shows them again, and the page remembers that choice too.

Several scopes can work one repo, so a scope **claims** each issue it plans to act on with an
`fr:claimed` label and a marker comment. Another scope's claim is hands-off. Taking one over
(`fr triage claim take`) or releasing it is the operator's call, never yours. When a scope
has stopped for good, `fr triage scope retire <id>` releases all its claims. For a closed
issue it also removes both `fr:` labels, because that issue's work is over. The
[herdr guide](../herdr-control-sessions.md) and the [cloud guide](../cloud-setup.md) cover
runners, restarts and the cloud driver. [The wave driver](fr-wave-driver.md) walks through
what one pass does and where you act.

## fr-origins: where did the bugs come from?

You can read an issue and the code it names. A classification done in chat dies with the
session; `fr triage origins` keeps it, so a re-run costs only what arrived.

```bash
fr triage origins collect --repo example-org/example-repo --since 2026-10-01
fr triage origins check   --repo example-org/example-repo
fr triage origins render  --repo example-org/example-repo
```

`collect` writes `origins-facts.json`; you write `origins.yaml`, one classification per
issue; `render` builds `origins.html`. Collect refuses a window wider than one page, and
names a `--since` that the page does cover. It also keeps the pull requests merged since
that date, so the page can show each one's title and merge date. The "Every issue" section
has a filter for open, closed or all issues and one fold for each category below, each with
its count; the filter updates the counts. In the list of pull requests that left work
behind, each row opens to the issues that name it. The PR list is read once per repo,
newest created first. When it comes back full, collect warns: a PR created before the
oldest one read but merged inside the window can lie beyond it, and then shows
"not collected". A pull request the file does not hold
(merged before the window, or collected by an older fr) shows "not collected". The categories describe what the defect *is*, not who noticed it:

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

## What does triage not do?

- The engine ranks nothing. Every tier is your judgement.
- `check` is as current as the last `collect`.
- Each render rewrites the pages; hand-written analysis goes in the fragments listed in
  each page's `manifest.yaml`, never in an edited page.
- Keep state and pages local for any repo that is not yours. A privacy guard refuses to
  batch a private repo's issue into a scope whose state repo is public.

## Where do you go next?

- [fr-goal](01-fr-goal.md) is the run a batch becomes (fr-debugging for a batch created
  with the debug skill).
- [fr-audit](fr-audit.md) draws the architecture page and the cost of a run.
- [fr-acceptance](fr-acceptance.md) covers the post-merge walks that keep an issue open.
