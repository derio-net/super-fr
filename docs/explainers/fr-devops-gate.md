---
title: "fr-devops-gate: When Merging Is Not the End"
date: 2026-11-11
draft: false
tldr: |
  Some changes need a human to do something outside the code: create a key, rotate a
  token, restart a service. fr-devops-gate is the one command that sequences those
  operations around the merge, records what happened, and refuses to skip a stage.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-devops-gate/SKILL.md
  - packages/fr/src/fr/ops/gate.py
  - packages/fr/src/fr/commands/ops_gate_cmd.py
  - packages/fr/src/fr/commands/gate_cmd.py
reviewed: 2026-11-12 placement-resolver phase 2, artifact directories now come from fr.artifacts.paths; the paths and behaviour this page describes are unchanged
---

## Overview: why a delivered PR can still be unfinished

Most runs end when the pull request is open and reviewed. A run whose plan carries
**manual operations** does not. Maybe the deploy key must exist before CI can pass,
or a secret must be rotated the minute the new code lands. Left as prose in a PR
description, those steps get done late, in the wrong order, or not at all, and nobody can
tell afterwards which happened.

fr turns each such operation into a typed record, an **op**, with a probe that says
whether it is done and, usually, a command that does it (the format is in the
[fr ops guide](../ops.md)). A run carrying ops, or whose spec declares `gate: devops`, is
held by the `devops` gate: its work is not finished at delivery. **The DevOps stage** is
what finishes it, and you run it as one command.

You reach for it when `fr pickup --run <id>` prints a DevOps brief, when the pull request
carries the label `gate:devops`, or when you want to apply a PR's operations and merge it.

## A worked example

The run id comes from the brief. Start with a preview, which changes nothing:

```bash
fr ops gate --run 2026-11-11-add-webhook-limiter
```

It lists the eight stages and where this run is. When that looks right:

```bash
fr ops gate --run 2026-11-11-add-webhook-limiter --yes
```

It works through the stages below, stopping and naming the stage at the first failure.
Stopping is always safe: run the same command again and it resumes at the first
unrecorded stage. Even with `--yes` the merge asks its own question. Read it. The PR
number and head must be the ones you reviewed, and the pre-merge state must list every
pre-merge op as closed.

The command runs on your machine, at a terminal, from a checkout that holds the run. It
refuses non-interactive contexts, so a delivering agent cannot run it: you type it, or you
watch an agent type it in your terminal. It needs a profile declared `ops: true`, which
`fr init scaffold --ops` writes (see [fr-init](fr-init.md)).

## The eight stages

| Stage | What happens |
|---|---|
| 1 | Refuses an ops gap, brings up the ops workspace `chore/ops-<slug>` on the ops profile, asks you to trust the op set if it changed, then runs pre-merge status and applies each open op after its own confirmation |
| 2 | Merges the PR, only with no open pre-merge op, green required checks and the head stage 1 verified |
| 3 | Verifies the merge, rebases the ops branch onto the default branch, runs every op's `ready:` probe |
| 4 | Post-merge status and apply |
| 5 | Probes each Test Plan step that points at an op, asks you about the rest, and records the outcomes |
| 6 | `fr gate pass --gate devops --run <id>`, from the ops workspace |
| 7 | Keeps `gate:tester` and lists the steps the Tester gate owns |
| 8 | `fr archive --branch <feature>`, then opens the ops branch as the housekeeping PR |

Each stage's completion is recorded in a state directory outside every checkout, by
default `~/.local/state/fr/ops-gate/`. Pre-merge evidence is committed only to the ops
branch, never to the PR head, so the reviewed head and its checks stay valid. A PR you
merged by hand in the forge counts as stage 2 done.

## Trust: probes are code from the repo

An op's `check:` is a shell command written in a pull request. Running it is running
repo-authored code, so `fr ops status` and the gate refuse to run any probe until you have
accepted that exact op set with `fr ops trust`. Trust is recorded in your own store outside
the repo, and only on the host. If the set changes, you are asked again. A PR whose diff
changes the ops profile itself is refused before anything comes up: it has to merge on its
own first.

## Reading what the stage tells you

An op is OPEN when its `check:` exited non-zero; the reason is the check's last line.
Decide what the reason says before confirming anything:

- **Simply not done yet** (a key absent, a secret unset): confirm the apply.
- **The check proves nothing**: `fr ops status --explain` shows what a vacuous probe looks
  like. Stop and fix the check in the plan.
- **CANNOT-VERIFY** (exit 127, an unreadable credential reference, a timeout): the
  environment is wrong, not the op. Fix the profile or identity, and never attest around it.
- **ESCALATE**: the condition the op guards against is already happening. Tell the owner
  before anything else.

## Attest, or write a check?

An op with no `check:` ends UNVERIFIABLE after its apply, and the gate asks for an
attestation: `fr ops attest <op> --note "<what you did and saw>"`, run at a terminal in
the ops workspace. Attesting is right only when no probe could tell, such as a click in a
UI with no API or a phone call. If any command could read the result, write that check
instead. A check runs every time and catches drift; an attestation is a statement about
one moment. An op that has a `check:` cannot be attested.

## The Test Plan steps and the tester hand-off

At stage 5, a step that points at an op is probed. A pass is recorded as `ran` with the
check's evidence and asks nothing. A failing probe shows its reason and asks `retry`,
`na <reason>` or `owed <why>`; `ran` is refused. A step with no pointer you walk
yourself and answer `ran <evidence>`, `na <reason>` or `owed <why>`. An `owed` answer is
recorded but does not close the step, so stage 6 refuses and prints the
`fr closeout outcome` command to record it once you have walked it. Steps the Tester gate
owns keep `gate:tester` on the PR and are not this stage's to walk.

## What the stage never does

- It never runs a probe of an untrusted op set.
- It never pushes to the PR head, and never merges a head it did not verify.
- It never skips a failed stage.
- It refuses a PR based on a branch other than the forge's default, or one touching the
  archived journals.

## Limits

- It cannot make an operation safe. `undo:` and `side_effects:` are shown at confirmation,
  and a mutating op also needs `--yes-mutating` when there is no terminal.
- On a forge fr cannot merge through, stage 2 stops and names the manual merge; do it at
  that head, then re-run.
- `gate:tester` and `gate:devops` are separate. Passing one does not pass the other.
- The repo's settings (`fr settings show`) can remove the stage entirely. Under
  `artifacts.gates: off` no gate is computed, labelled or held, so there is no DevOps stage.
  Under `forge.labels: off` there is no gate label to pass. Under `forge.comments: off`,
  `fr gate pass` swaps the label without commenting and closes no tracker, so record what
  passed the gate in the run's journal.

## Where to go next

- The [fr ops guide](../ops.md) is how to author an op.
- [fr-acceptance](fr-acceptance.md) covers the rows and walks that also hold a merge's
  close-out.
- [fr-goal](01-fr-goal.md) is the run that produces the PR this stage finishes.
