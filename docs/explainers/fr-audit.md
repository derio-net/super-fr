---
title: "fr-audit: What a Run Actually Cost"
date: 2026-11-11
draft: false
tldr: |
  A pipeline you cannot measure is a pipeline you cannot improve. fr-audit reads what
  the harness itself recorded and splits the money across activities and steps. It lets
  you compare runs before and after a process change, and you never price a token by hand.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-audit/SKILL.md
  - packages/fr/src/fr/usage/**
  - packages/fr/src/fr/commands/usage_cmd.py
  - packages/fr/src/fr/triage/architecture.py
reviewed: 2026-11-12 placement-resolver phase 2, artifact directories now come from fr.artifacts.paths; the paths and behaviour this page describes are unchanged
---

## Why not compute the numbers yourself?

Someone asks "what did that run cost, and where did the money go?" It is tempting to
estimate. fr refuses to. `fr usage` reads the harness's own records: Claude Code
transcripts, and OpenCode and Hermes databases, opened read-only. It takes the dollar
figure the harness reports and splits it across what the session was doing. fr never
invents a list price.

The skill's job is the part a tool cannot do: choose what to compare, and say what it
means. You reach for it in these cases:

- Someone asks what a run or session cost.
- Someone asks whether a process change made the pipeline cheaper.
- You need an audit page or an architecture page.
- A pull request body needs its usage table.

## A worked example

Last month you changed how you cut plans into phases. Now you want to know whether runs got
cheaper.

```bash
fr usage compare --before 2026-10-15 --after 2026-10-15
```

`--before` takes the runs that started before the cutoff; `--after` takes those at or
after it. Both accept an ISO (International Organization for Standardization) date, a
timestamp or a run id. The output reads committed usage files, run cursors and plan
journals. For each set it shows:

- the phases and turns;
- the main-session and subagent tokens;
- the cost, and how many runs had a price;
- the review findings per phase, and the re-opened findings.

It gives per-run rows and per-set medians and `n`. Add `--steps` for the main session's
turns, tokens, cost and dollars-per-turn at each pipeline step.

What you say about it matters more than the table. Quote the command and the output, with
`n` and the priced count. Say **inconclusive** when the sets are thin or confounded: a
model change between the sets, unpriced runs, or runs from before fr recorded the figures.

To look at one run:

```bash
fr usage collect --run 2026-11-11-add-webhook-limiter
fr usage report  --run 2026-11-11-add-webhook-limiter --format table
fr run cost 2026-11-11-add-webhook-limiter
```

`collect` normalises every session the run's cursor records into `$HOME/.cache/fr/usage/`.
`report` prints cost per model, activity, sub-activity and step. `fr run cost` prints the
per-step and per-model cost from the run's committed usage file. A figure nobody could
observe prints as `—`, never as zero.

## Which commands are there?

| Command | What it does |
|---|---|
| `fr usage collect --run <id>` | every session a run cursor records |
| `fr usage collect --session <id> [--harness opencode\|hermes]` | one session; Claude Code is the default harness |
| `fr usage report --run <id> ... --format table` | the split, as a table |
| `fr usage report --session <id> ... --format html -o <file>` | the same as one self-contained page |
| `fr usage compare --before X --after Y` | two sets of runs, side by side |
| `fr usage backfill` | writes the committed usage file for archived runs that have none |

`collect` and `report` write only under the cache, except the page `report -o <file>`
writes where you point it. `compare` reads committed files and writes nothing. Pass
`--repo <path>` when the cursors live in another checkout. These commands run on the
harness host: `fr isolation exec` refuses them inside a devcontainer.

## How do you read the split?

- **Dollars are the harness's.** fr divides each model's figure over that model's
  messages by price-weighted tokens. It uses fixed ratios: input 1, cache write 1.25 for
  five minutes or 2 for an hour, cache read 0.1, output 5. The split always sums back to
  the harness total. Whatever no message carries lands in `other / unattributed`.
- **Activities.** *Paperwork* is fr's own bookkeeping: specs, plans, journals, cursors,
  the acceptance matrix and learning the CLI. *Implementation* is code read, code written
  and verification. *Other* is version control, orchestration and narration.
- **Context carry, not generation, dominates.** In a long session most of the dollars are
  cache reads: the agent re-reads the whole context on every turn. A turn late in a session
  costs far more than the same turn early; output is the small part.
- **Turns are the cost unit.** A bookkeeping step that takes six turns costs six re-reads,
  however little it writes. When paperwork looks expensive, count its turns before you
  blame its size.
- **`source`** is `exact` (the billed figure), `estimated` (the harness's estimate) or
  `none`. Carry it into any claim.

A session another host ran comes back `unavailable` and renders `—`. That is an absence,
not a cheap session. Never drop it silently, and never count it as zero.

## How do you build the pages?

The audit page is `fr usage report --session <id> ... --format html -o <file>`. Report the
pooled shares and the per-session range, name the sessions, and state what was
unavailable.

The engine builds the **architecture page** from three inputs you write in the triage
state directory:

```bash
fr triage architecture render --repo example-org/example-repo --now-ref HEAD
```

`subsystems.yaml` lists the subsystems. For each one it gives the name, the path globs,
the git ref fr measures "then" at, and the judgement themes that place an open issue on
it. `architecture/<name>.html` holds authored fragments, and `architecture/manifest.yaml`
orders them with the generated sections. The generated sections (summary, subsystem cards,
size table) are measurements: lines counted at each ref.

Everything you author is the future state. So label every such figure a **projection**,
in the fragment itself. When the change ships, render again and put the measured figure
beside it. A projection presented as a measurement is the defect the skill exists to
prevent. Fragments refuse scripts, styles, forms and `on*` attributes, and must carry no
untrusted text. See [fr-triage](fr-triage.md) for the other pages in that family.

## What are the red flags?

- A share quoted with no session list or no `source`.
- `—` turned into `0`, or an unavailable session left out of the story.
- A dollar figure computed from a list price.
- A before and after claim across runs of different shape or harness, left unstated.
- Session ids, paths or model names pasted into a public artifact unredacted.

## What can it not do?

- Hermes keeps one token count per message, so its split is token-weighted and marked
  `coarse attribution`. State that when you compare.
- You can read a transcript only on the host that holds it.
- Publishing a page stays your job: fr writes a file, and you redact it before it leaves
  your machine.

## Where do you go next?

- [fr-goal](01-fr-goal.md) is the run most audits look at.
- [fr-brainstorming-and-plan](fr-brainstorming-and-plan.md) explains the phase sizing that
  drives the fixed cost per phase.
