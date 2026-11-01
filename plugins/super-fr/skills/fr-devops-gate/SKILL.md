---
name: fr-devops-gate
description: >
  Use when a delivered run's effective gates include devops (its plan carries manual
  operations, or its spec declares `gate: devops`), when `fr pickup --run` prints a DevOps
  brief, or when the operator asks to run the DevOps stage, apply a PR's manual operations,
  or merge a PR that gate:devops holds.
---

# fr-devops-gate

**Announce at start:** "I'm using fr-devops-gate to run the DevOps stage of run <id>."

A run whose plan carries ops does not end at `deliver`. Its DevOps stage applies the
pre-merge ops, merges the PR, applies the post-merge ops, records the devops Test Plan
steps, passes `gate:devops`, hands the tester steps to the Tester gate and archives. One
command drives all of it; this skill holds only the judgement the command cannot.

## The command

```bash
fr ops gate --run <run-id>          # preview the 8 stages; changes nothing
fr ops gate --run <run-id> --yes    # act; resumes at the first unrecorded stage
```

It runs on the harness host at a terminal, from a checkout that holds the run (the
feature workspace, or the base clone once the PR merged). It refuses a non-interactive
context, so a delivering agent cannot run it: the operator types it, or watches you run
it in their terminal. It needs a profile declared `ops: true` (`fr init scaffold --ops`
writes one).

| Stage | What it does |
|---|---|
| 1 | Refuses an ops gap (a devops-gated run with command steps and no op, no `none:`), reading the PR head, or the default branch's tip once merged; then brings up the ops workspace `chore/ops-<slug>` from the PR head (from the default branch once the PR merged) on the ops profile, asks you to trust the op set when it changed (`fr ops trust`, on the host), then runs pre-merge status and applies each open op after its own confirmation |
| 2 | Merges the PR, only with no open pre-merge op, green required checks, the head stage 1 verified, and a confirmation naming the PR, its head and the pre-merge state |
| 3 | `fr isolation verify-merge`, rebases the ops branch onto the default branch, runs every `ready:` |
| 4 | Post-merge status and apply |
| 5 | Probes each `(op: <id>)` step, asks for the others' outcome, and records it (`fr closeout outcome`) |
| 6 | `fr gate pass --gate devops --run <id>` from the ops workspace |
| 7 | Keeps `gate:tester` and lists the steps the Tester gate owns |
| 8 | `fr archive --branch <feature>`, then opens the ops branch as the housekeeping PR |

Each stage's completion is recorded in your own state outside every checkout
(`~/.local/state/fr/ops-gate/` by default); before the merge the ops branch is only
committed locally (it still holds the unmerged PR), and from stage 3 on a stage counts
only once its record is pushed. The `gate-stage-<n>` journal decisions are an audit
trail. The default branch is the forge's, checked against `origin/HEAD`; a PR based
elsewhere, or touching the archived journals, is refused. The PR controls
the ops workspace, so inside the stage an op closes only by its live check, and an
attestation or Test Plan outcome only when added on the ops branch, never one the PR
already carries. A PR whose own diff changes the ops profile is refused before anything
comes up (it merges in its own PR first), and so is a cut whose profile is not the
default branch's (rebase an open PR onto it). So stopping is always safe: re-run
the same command. Pre-merge evidence never lands on the PR head, so
the reviewed head and its checks stay valid. A PR merged by hand in the forge counts as
stage 2 done.

## Reading an OPEN reason

An op is OPEN when its `check:` exited non-zero; the reason is the check's last line
(masked; a body-like line shows only `exit N`). Decide what the reason says before
confirming anything:

- **The op simply is not done yet** (a key absent, a secret unset): confirm the apply.
- **The check proves nothing** (`fr ops status --explain` shows the op's `vacuous_if:`):
  stop and fix the check in the plan; the trust prompt then shows the change.
- **CANNOT-VERIFY** (exit 127, a credential reference that could not be read, a timeout):
  the environment is wrong, not the op. Fix the profile or the identity, never attest.
- **ESCALATE**: the condition the op guards against is already happening. Tell the
  operator before anything else.

## Attest, or write a check?

An op with no `check:` ends UNVERIFIABLE after its apply, and the stage stops asking
for an attestation. Attesting (`fr isolation exec --branch chore/ops-<slug> -- fr ops
attest <op> --note "<what you did and saw>" --plan <plan>`, at a terminal) is right
only when no probe could tell: a click in a UI with no API, a phone call. If any
command could read the result (an API, a CLI, a file the op wrote), write that `check:`
instead: a check runs every time and catches drift; an attestation is a statement about
one moment. An op that has a `check:` cannot be attested.

## Confirming the merge

The merge asks its own question even under `--yes`. Before answering yes, read it:
the PR number and head must be the ones you reviewed, and the pre-merge state must list
every pre-merge op as closed. If the head moved since stage 1, the stage refuses and
names the way back (take the ops workspace down and re-run, which re-cuts it from the
new head and re-checks trust). On a forge fr cannot merge through, the stage stops
naming the manual merge; merge in the forge at that head, then re-run.

## Devops steps and the tester hand-off

Stage 5 runs the probe of each step that points at an op (`(op: <id>)`). A passing check
records `ran` with the check's evidence lines and asks nothing. A probe that fails (OPEN,
UNVERIFIABLE, CANNOT-VERIFY, ESCALATE) shows its reason and asks `retry`, `na <reason>` or
`owed <why>`; `ran` is refused. A step with no pointer, an N/A op or one closed without a
check is walked by you, then answered `ran <evidence>`, `na <reason>` or `owed <why>` (`ran: x`
works too; an answer that does not match is asked again). Committed evidence is only a few
status lines, so a probe should end with a one-line summary. An `owed` answer is recorded but does not close the step,
so stage 6 refuses and prints the `fr closeout outcome` command that records it once you
have walked it (a later `ran`/`na` supersedes the owed one); then re-run the stage. Steps the Tester gate
owns are listed in the gate-pass comment and keep `gate:tester` on the PR; they are not
this stage's to walk.

## What the stage never does

- It never runs a probe of an untrusted op set, and trust is granted only on the host.
- It never pushes to the PR head, and never merges a head it did not verify.
- It never skips a failed stage: the first failure stops the run, naming the stage.
