---
title: "From an Idea to a Plan Your Agent Can Execute"
date: 2026-11-11
draft: false
tldr: |
  Before anyone writes code, three skills turn a loose idea into a spec you can hold the
  agent to and a plan it can tick off. fr-brainstorming designs the thing in isolation,
  fr-plan cuts it into phases, and fr-execute builds one phase at a time, test first.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-brainstorming/SKILL.md
  - plugins/super-fr/skills/fr-plan/SKILL.md
  - plugins/super-fr/skills/fr-execute/SKILL.md
  - packages/fr/src/fr/commands/plan_cmd.py
  - packages/fr/src/fr/commands/pickup_cmd.py
reviewed: 2026-11-14 quiet/stealth plans, deliver and close-out read artifacts where they live (debug 2026-11-13-placement-plan-paths)
---

## Why write the idea down twice?

An agent that starts coding from a sentence will build something. Whether it is the
thing you meant is luck. fr puts two documents between the sentence and the code. It
makes the second one mechanical enough that a machine can check it.

The first document is the **spec**: what must be true when the work is done, written as
a numbered list of requirements. The second is the **plan**: the spec cut into phases,
tasks and steps, each with an id. So progress is a fact on disk instead of a claim in a
chat. Three skills own this stretch:

- **fr-brainstorming** produces the spec, inside an isolated workspace.
- **fr-plan** produces the plan folder from the spec.
- **fr-execute** is what an agent follows to implement one phase of that plan.

You rarely call them yourself. [fr-goal](01-fr-goal.md) runs all three in order. You
reach for them directly in three cases:

- You want only the design (stop after brainstorming).
- You want a plan for work you have already specified.
- You are picking up one phase by hand.

## A worked example

You want rate limiting on a webhook receiver, and you want the design settled before
anyone builds anything.

```bash
fr isolation up --branch feat/webhook-rate-limit
```

That is the first command, always. [fr-isolation](fr-isolation.md) creates a worktree
outside your clone. So the exploration, the spec draft and the later build share one
branch, and your checkout stays untouched. From inside it you brainstorm. The agent reads
the code, asks what it cannot decide for you, and proposes approaches. It writes the result
to `docs/superpowers/specs/<date>-webhook-rate-limit-design.md`.

With the spec committed, the plan comes next. Describe the phases in a scratch file
outside the repository (git would commit a draft inside it with the plan). A one-phase
plan is enough to start:

```yaml
# $TMPDIR/phases.yaml
- number: 1
  title: Rate-limit the webhook endpoint
  tag: agentic
  depends_on: []
  tier: standard
  tasks:
    - number: 1
      title: Token bucket per sender
      steps:
        - {id: P1.T1.S1, text: "RED: a test that the 11th request in a second gets HTTP 429."}
        - {id: P1.T1.S2, text: "GREEN: add the bucket and return 429 when it is empty."}
        - {id: P1.T1.S3, text: "REFACTOR: move the limits into config."}
```

`--prose-file` is the plan's narrative in Markdown. Leave it out, and fr writes a stub.

```bash
fr plan create --slug 2026-11-11-webhook-rate-limit \
    --target-repo example-org/example-repo \
    --spec docs/superpowers/specs/2026-11-11-webhook-rate-limit-design.md \
    --phases-file "$TMPDIR/phases.yaml"
fr plan self-review docs/superpowers/plans/2026-11-11-webhook-rate-limit
```

`create` scaffolds `docs/superpowers/plans/<slug>/` and adds a row to the spec's
`## Implementation Plans` table. In a quiet repository the same folder sits below the
feature's own path on the `fr` branch instead, and nothing lands on the feature branch.
`self-review` lints what the schema cannot: a missing tier, a phase that cites no
requirement, a step that tells an agent to dispatch another agent.

An agent then takes phase 1:

```bash
fr pickup docs/superpowers/plans/2026-11-11-webhook-rate-limit --phase 1
fr plan edit docs/superpowers/plans/2026-11-11-webhook-rate-limit --tick P1.T1.S1
fr plan edit docs/superpowers/plans/2026-11-11-webhook-rate-limit --complete-phase 1
```

`pickup` prints the phase as Markdown: title, dependencies, tasks and steps, and the
plan's prose. `--tick` marks a step done. `--complete-phase` closes the phase once every
step has its tick.

## What does fr-brainstorming add?

It is the ordinary brainstorming discipline (understand the goal, explore, propose
approaches, refine) with one change: **isolation comes before everything**, even a
harmless-looking read. If the branch is `feat/<slug>` from the first command, a
brainstorm that turns into a build never has to move. One that dies leaves your checkout
as it was. In devcontainer mode a repo with no profile is a hard stop (the skill offers
the [fr-init](fr-init.md) interview); a docker-less host skips that.

It adds four things to a plain brainstorm:

- **The brief, recorded.** The skill saves the operator's request verbatim as a
  spec-journal entry (`fr journal add --scope spec --slug <spec-slug> --kind discovery --input
  --title "..." --body "..."`), after it redacts any third-party names. Nothing downstream
  reads it. The spec is the contract, and nobody builds a requirement the spec does not
  state.
- **A `## Requirements` section** before `## Design`: one line each, `R1. ...`, `R2. ...`.
  Plans and acceptance rows cite these ids.
- **The verification question.** Every brainstorm asks once how you will prove the change
  before merge. `fr verification list` shows the available strategies. The answer goes in
  the spec's `## Verification` section. See
  [verification strategies](../verification-strategies.md).
- **Acceptance rows, presented.** Each requirement, or closely related group of
  requirements, gets a row in the acceptance matrix that says what the product does (see
  [fr-acceptance](fr-acceptance.md)). The brainstorm ends by showing you those rows, with
  a one-line defense each. Silently creating them is not you accepting the scope; seeing
  them is.

Standalone, it is fully interactive: it asks questions as they arise. Under fr-goal, it
collects the questions into one round instead.

## What is in an fr-plan folder?

A plan is a directory, not a document. Per-phase files keep two branches that tick
different phases from conflicting.

- `_meta.yaml`: the plan's slug, spec reference, target repo and schema version.
- `_prose.md`: the narrative for humans. Tooling never parses it.
- `01.yaml`, `02.yaml`, ...: one file per phase, with its header, tasks and steps.

Every step id has the shape `P<phase>.T<task>.S<step>`. Everything else (progress
reports, GitHub tracking, the executor's ticks) depends on that shape.

The rules the skill applies when it writes a plan:

- **Test first.** Each task is red, green, refactor, or it records why there was nothing
  to clean.
- **Few phases.** One phase per independently reviewable ask. A phase costs a fixed
  round trip however small it is, so a one-phase plan is often right. Every phase after
  the first needs a recorded reason for existing.
- **Agentic phases are fully agent-completable.** Secrets, UI operations and deploys go
  in a separate `[manual]` phase, never hidden inside an agentic one.
- **Steps name outcomes, not mechanisms.** "Gather evidence following the protocol",
  never "dispatch the reviewer". A step that names a tool rots silently when the tool
  changes, and the executor cannot dispatch anyway.
- **Each agentic phase declares a tier**: `mechanical`, `standard` or `hard`. The tier is
  a hint that `fr models resolve` turns into a model. `hard` needs a written
  justification, because it sends the whole phase to the costliest one.
- **Acceptance linkage and `files:`.** A phase lists the matrix rows it advances and the
  paths it expects to touch. So `fr plan proportionality` can report work outside the
  plan at delivery.

After a plan ships, items that surfaced but were never built go into a sibling rework
plan. You do not reopen the parent. Run `fr plan rework <parent-plan-dir>` (the parent may
be live or archived; fr does not check that it is complete). Then run
`fr plan rework-add` to record each item and `fr plan rework-list` to see what is open.

## How does fr-execute run one phase?

The executor works from `fr pickup`. If the phase's dependencies are not complete, it
stops and says so. Otherwise it implements task by task and ticks each step as it
finishes (or `--state - --note "<reason>"` for a deliberate skip). It completes the phase
when every step has its tick.

Inside an fr-goal run, `pickup` ends with a **step record** template. The executor fills
that in (ticks, refactor reasons, what it learned) instead of calling the tick verbs. The
orchestrator applies the whole record in one commit. That is what makes a phase's outcome
a durable artifact instead of a summary.

Constraints worth knowing:

- An executor is a leaf. A step that tells it to dispatch or delegate is a **blocker**:
  the executor reports that, leaves the step unticked and does not complete the phase. To
  do the work inline would defeat the point of dispatching it.
- It touches only its own phase. Under fr-goal it does not open a pull request; the
  orchestrator opens the single PR after review.
- Outside fr-goal, in the dispatched flow, a phase gets its own PR, titled
  `[owner/repo] slug · Phase n/total · title`. `fr apply` pushes the label changes
  (`fr:ready`, `fr:in-progress`, `fr:pr-ready`) that it derives from the issue and its
  PRs. See [fr-dispatch](fr-dispatch.md).

## What do the skills not do?

- The skills cover *where* and *in what shape* the work happens. They do not cover the
  craft of brainstorming or test-driven development: they delegate that to the underlying
  superpowers skills, unchanged.
- `fr plan self-review` is a lint, not a proof. It cannot tell whether a spec's
  requirements are the right ones.
- What a spec and plan contain depends on the repo's settings (`fr settings show`).
  Under `artifacts.acceptance: off` there are no acceptance rows to present or link.
  Under `test_plan: off` there is no Test Plan. Under `gates: off` there is no gate split.
  You can never turn off the spec, the plan or the journals themselves.
- Outside fr-goal, the executor pushes with `fr push` and opens its draft with
  `fr pr create`, never `git push` or the forge's CLI, so the repo's git policy applies.
- A plan that is a single `.md` file is the old v1 format. `fr migrate v1-to-v2 --yes`
  converts every completed v1 plan in the repo at once (add `--include-in-progress` for
  the rest). Commit that as its own change.

## Where do you go next?

- [fr-goal](01-fr-goal.md) runs this whole sequence unattended.
- [fr-isolation](fr-isolation.md) explains the workspace all three skills run in.
- [fr-progress](fr-progress.md) shows where a plan stands.
- [fr-dispatch](fr-dispatch.md) queues a plan's phases to a runner.
