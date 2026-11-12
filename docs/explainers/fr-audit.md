---
title: "fr-audit: What a Run Actually Cost"
date: 2026-11-11
draft: false
tldr: |
  A pipeline you cannot measure is a pipeline you cannot improve. fr-audit reads what
  the harness itself recorded, splits the money across activities and steps, and lets you
  compare runs before and after a process change, without ever pricing a token by hand.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-audit/SKILL.md
  - packages/fr/src/fr/usage/**
  - packages/fr/src/fr/commands/usage_cmd.py
  - packages/fr/src/fr/triage/architecture.py
reviewed: 2026-11-12 placement-resolver phase 2, artifact directories now come from fr.artifacts.paths; the paths and behaviour this page describes are unchanged
---

## Overview: the numbers are not yours to compute

When someone asks "what did that run cost, and where did the money go?", the temptation is
to estimate. fr refuses to: `fr usage` reads the harness's own records (Claude Code
transcripts, OpenCode and Hermes databases, opened read-only), takes the dollar figure the
harness reports, and splits it across what the session was doing. fr never invents a list
price.

The skill's job is the part a tool cannot do: choosing what to compare and saying what it
means. You reach for it when asked what a run or session cost, whether a process change made
the pipeline cheaper, for an audit page or an architecture page, or when a pull request body
needs its usage table.

## A worked example

You changed how plans are cut into phases last month and want to know whether runs got cheaper.

```bash
fr usage compare --before 2026-10-15 --after 2026-10-15
```

`--before` takes the runs that started before the cutoff; `--after` takes those at or after it.
Both accept an ISO date, a timestamp or a run id. The output reads committed usage files, run
cursors and plan journals, and shows for each set the phases, turns, main-session and subagent
tokens, cost (and how many runs were actually priced), review findings per phase and re-opened
findings, with per-run rows and per-set medians and `n`. Add `--steps` for the main session's
turns, tokens, cost and dollars-per-turn at each pipeline step.

What you say about it matters more than the table. Quote the command and the output with `n` and
the priced count, and say **inconclusive** when the sets are thin or confounded: a model change
between the sets, unpriced runs, or runs from before the figures were recorded.

To look at one run:

```bash
fr usage collect --run 2026-11-11-add-webhook-limiter
fr usage report  --run 2026-11-11-add-webhook-limiter --format table
fr run cost 2026-11-11-add-webhook-limiter
```

`collect` normalises every session the run's cursor records into `$HOME/.cache/fr/usage/`;
`report` prints cost per model, activity, sub-activity and step. `fr run cost` prints the
per-step and per-model cost from the run's committed usage file. A figure nobody could observe
prints as `—`, never as zero.

## The commands

| Command | What it does |
|---|---|
| `fr usage collect --run <id>` | every session a run cursor records |
| `fr usage collect --session <id> [--harness opencode\|hermes]` | one session; Claude Code is the default harness |
| `fr usage report --run <id> ... --format table` | the split, as a table |
| `fr usage report --session <id> ... --format html -o <file>` | the same as one self-contained page |
| `fr usage compare --before X --after Y` | two sets of runs, side by side |
| `fr usage backfill` | writes the committed usage file for archived runs that have none |

`collect` and `report` write only under the cache, except the page `report -o <file>` writes
where you point it. `compare` reads committed files and writes
nothing. Pass `--repo <path>` when the cursors live in another checkout. These commands run on the
harness host: `fr isolation exec` refuses them inside a devcontainer.

## Reading the split

- **Dollars are the harness's.** Each model's figure is divided over that model's messages by
  price-weighted tokens, using fixed ratios (input 1, cache write 1.25 for five minutes or 2 for
  an hour, cache read 0.1, output 5). The split always sums back to the harness total. Whatever no
  message carries lands in `other / unattributed`.
- **Activities.** *Paperwork* is fr's own bookkeeping: specs, plans, journals, cursors, the
  acceptance matrix and learning the CLI. *Implementation* is code read, code written and
  verification. *Other* is version control, orchestration and narration.
- **Context carry, not generation, dominates.** In a long session most of the dollars are cache
  reads, the whole context re-read on every turn. A turn late in a session costs far more than the
  same turn early; output is the small part.
- **Turns are the cost unit.** A bookkeeping step that takes six turns costs six re-reads however
  little it writes. When paperwork looks expensive, count its turns before blaming its size.
- **`source`** is `exact` (the billed figure), `estimated` (the harness's estimate) or `none`.
  Carry it into any claim.

A session another host ran comes back `unavailable` and renders `—`. That is an absence, not a
cheap session: never drop it silently and never count it as zero.

## The pages

The audit page is `fr usage report --session <id> ... --format html -o <file>`. Report the pooled
shares and the per-session range, name the sessions, and state what was unavailable.

The **architecture page** is built by the engine from three inputs you write in the triage state
directory:

```bash
fr triage architecture render --repo example-org/example-repo --now-ref HEAD
```

`subsystems.yaml` lists subsystems (name, path globs, the git ref "then" is measured at, and the
judgement themes that place an open issue on it). `architecture/<name>.html` holds authored
fragments, and `architecture/manifest.yaml` orders them with the generated sections. The generated
sections (summary, subsystem cards, size table) are measurements: lines counted at each ref.
Everything you author is the future state, so label every such figure a **projection**, in the
fragment itself, and when the change ships render again and put the measured figure beside it. A
projection presented as a measurement is the defect the skill exists to prevent. Fragments refuse
scripts, styles, forms and `on*` attributes, and must carry no untrusted text. See
[fr-triage](fr-triage.md) for the other pages in that family.

## Red flags

- A share quoted with no session list or no `source`.
- `—` turned into `0`, or an unavailable session left out of the story.
- A dollar figure computed from a list price.
- A before and after claim across runs of different shape or harness, left unstated.
- Session ids, paths or model names pasted into a public artifact unredacted.

## Limits

- Hermes keeps one token count per message, so its split is token-weighted and marked
  `coarse attribution`. State that when comparing.
- Reading a transcript is only possible on the host that holds it.
- Publishing a page stays yours: fr writes a file, and you redact it before it leaves your machine.

## Where to go next

- [fr-goal](01-fr-goal.md) is the run most audits look at.
- [fr-brainstorming-and-plan](fr-brainstorming-and-plan.md) explains the phase sizing that drives
  the fixed cost per phase.
