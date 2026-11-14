---
title: "fr-devops-gate: When Merging Is Not the End"
date: 2026-11-11
draft: false
tldr: |
  Some changes need a human to do something outside the code: create a key, rotate a
  token, restart a service. fr-devops-gate is the one command that sequences those
  operations around the merge and records what happened. It refuses to skip a stage.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-devops-gate/SKILL.md
  - packages/fr/src/fr/ops/gate.py
  - packages/fr/src/fr/commands/ops_gate_cmd.py
  - packages/fr/src/fr/commands/gate_cmd.py
reviewed: 2026-11-14 quiet/stealth plans, deliver and close-out read artifacts where they live (debug 2026-11-13-placement-plan-paths)
---

## Why can a delivered PR still have work left?

The DevOps stage is one of two post-merge gates. [Exit gates](fr-exit-gates.md) explains how a run gets a gate and how gates hold the release.

Most runs end when the pull request is open and reviewed. A run whose plan carries
**manual operations** does not. Maybe the deploy key must exist before CI can pass. Or
someone must rotate a secret the minute the new code lands. Left as prose in a PR
description, those steps get done late, in the wrong order, or not at all. And nobody can
tell afterwards which happened.

fr turns each such operation into a typed record, an **op**. An op has a probe that says
whether it is done and, usually, a command that does it (the format is in the
[fr ops guide](../ops.md)). The `devops` gate holds a run that carries ops, or whose spec
declares `gate: devops`: delivery does not finish its work. **The DevOps stage** is what
finishes it, and you run it as one command.

You reach for it in these cases:

- `fr pickup --run <id>` prints a DevOps brief.
- The pull request carries the label `gate:devops`.
- You want to apply a PR's operations and merge it.

## A worked example

The run id comes from the brief. Start with a preview, which changes nothing:

```bash
fr ops gate --run 2026-11-11-add-webhook-limiter
```

It lists the eight stages and where this run is. When that looks right:

```bash
fr ops gate --run 2026-11-11-add-webhook-limiter --yes
```

It works through the stages below. At the first failure it stops and names the stage. It
is always safe to stop: run the same command again, and it resumes at the first stage
with no record. Even with `--yes`, the merge asks its own question. Read it. The PR number
and head must be the ones you reviewed, and the pre-merge state must list every pre-merge
op as closed.

The command runs on your machine, at a terminal, from a checkout that holds the run. It
refuses non-interactive contexts, so a delivering agent cannot run it. You type it, or you
watch an agent type it in your terminal. It needs a profile declared `ops: true`, which
`fr init scaffold --ops` writes (see [fr-init](fr-init.md)).

## What are the eight stages?

| Stage | What happens |
|---|---|
| 1 | Refuses an ops gap. Brings up the ops workspace `chore/ops-<slug>` on the ops profile. Asks you to trust the op set if it changed. Then runs pre-merge status and applies each open op after its own confirmation |
| 2 | Merges the PR, only with no open pre-merge op, green required checks and the head stage 1 verified |
| 3 | Verifies the merge, rebases the ops branch onto the default branch, and runs every op's `ready:` probe |
| 4 | Post-merge status and apply |
| 5 | Probes each Test Plan step that points at an op, asks you about the rest, and records the outcomes |
| 6 | `fr gate pass --gate devops --run <id>`, from the ops workspace |
| 7 | Keeps `gate:tester` and lists the steps the Tester gate owns |
| 8 | `fr archive --branch <feature>`, then opens the ops branch as the housekeeping PR |

fr records each stage's completion in a state directory outside every checkout. By
default that is `~/.local/state/fr/ops-gate/`. fr commits pre-merge evidence only to the
ops branch, never to the PR head, so the reviewed head and its checks stay valid. A PR you
merged by hand in the forge counts as stage 2 done.

## Why must you trust the probes?

An op's `check:` is a shell command written in a pull request. To run it is to run code
from the repo. So `fr ops status` and the gate refuse to run any probe until you have
accepted that exact op set with `fr ops trust`. fr records trust in your own store outside
the repo, and only on the host. If the set changes, fr asks you again. fr refuses a PR
whose diff changes the ops profile itself before anything comes up: that PR has to merge
on its own first.

## How do you read what the stage tells you?

An op is OPEN when its `check:` exited non-zero; the reason is the check's last line.
Decide what the reason says before you confirm anything:

- **Simply not done yet** (a key absent, a secret unset): confirm the apply.
- **The check proves nothing**: `fr ops status --explain` shows what a vacuous probe looks
  like. Stop and fix the check in the plan.
- **CANNOT-VERIFY** (exit 127, an unreadable credential reference, a timeout): the
  environment is wrong, not the op. Fix the profile or identity, and never attest around it.
- **ESCALATE**: the condition the op guards against is already happening. Tell the owner
  before anything else.

## Should you attest, or write a check?

An op with no `check:` ends UNVERIFIABLE after its apply, and the gate asks for an
attestation: `fr ops attest <op> --note "<what you did and saw>"`. Run it at a terminal in
the ops workspace. An attestation is right only when no probe could tell, such as a click
in a UI with no API, or a phone call. If any command could read the result, write that
check instead. A check runs every time and catches drift; an attestation is a statement
about one moment. You cannot attest an op that has a `check:`.

## What happens to the Test Plan steps?

At stage 5, the stage probes each step that points at an op. A pass goes on record as
`ran`, with the check's evidence, and asks nothing. A failing probe shows its reason and
asks `retry`, `na <reason>` or `owed <why>`; it refuses `ran`. You walk a step with no
pointer yourself and answer `ran <evidence>`, `na <reason>` or `owed <why>`.

fr records an `owed` answer, but it does not close the step. So stage 6 refuses, and
prints the `fr closeout outcome` command to record the outcome once you have walked it.
Steps the Tester gate owns keep `gate:tester` on the PR, and this stage does not walk
them.

## What does the stage never do?

- It never runs a probe of an untrusted op set.
- It never pushes to the PR head, and never merges a head it did not verify.
- It never skips a failed stage.
- It refuses a PR based on a branch other than the forge's default, or one that touches
  the archived journals.

## What can it not do?

- It cannot make an op safe. It shows `undo:` and `side_effects:` at confirmation. A
  mutating op also needs `--yes-mutating` when there is no terminal.
- On a forge fr cannot merge through, stage 2 stops and names the manual merge. Do it at
  that head, then run the command again.
- `gate:tester` and `gate:devops` are separate. Passing one does not pass the other.
- The repo's settings (`fr settings show`) can remove the stage entirely. Under
  `artifacts.gates: off`, fr computes, labels and holds no gate, so there is no DevOps
  stage. Under `forge.labels: off` there is no gate label to pass. Under
  `forge.comments: off`, `fr gate pass` swaps the label without a comment and closes no
  tracker. So record what passed the gate in the run's journal.

## Where do you go next?

- The [fr ops guide](../ops.md) is how to author an op.
- [fr-acceptance](fr-acceptance.md) covers the rows and walks that also hold a merge's
  close-out.
- [fr-goal](01-fr-goal.md) is the run that produces the PR this stage finishes.
