---
title: "fr-goal: One Conversation, Then a Reviewed Pull Request"
date: 2026-07-17
draft: false
weight: 2
series: [explainers]
post_number: 1
archetype: skill-presentation
tldr: |
  Tell fr-goal what outcome you want, answer one round of questions, and it
  carries the work to a pull request. The sequence it follows is not buried in
  the tool: it is a workflow shape, a short YAML file listing the steps, which
  your own repository can extend or replace. Before the first step runs,
  `fr run start` creates a separate Git worktree and development container, so
  the autonomous run cannot wander through your original checkout, and it keeps
  a durable record of the run's progress on the feature branch, so the journey
  can be reviewed or picked back up instead of vanishing with the chat. Inside
  that boundary the agent writes down the design, breaks the work into
  checkable pieces, builds each piece, runs acceptance tests, reviews it, and
  fixes what the review finds. After merge, the agent can guide you through a
  manual Test Plan in the real environment. You remain responsible for human
  decisions, privileged actions, and the final merge.
tags: ["fr-goal", "agent-workflows", "automation", "pull-requests"]
target: "."
standalone: true
standalone_style: broadsheet
---

## Overview

Imagine handing a capable development team a short description of a feature.
The team studies the existing product, asks one organized set of questions,
then designs, builds, tests, and reviews the change. You return when a pull
request is ready for your review. `fr-goal` gives an AI coding agent that shape
of responsibility.

The important idea is not "the agent writes code by itself." The important
idea is that the agent owns the **whole journey** from an outcome to a reviewed
change. It does not repeatedly ask you to approve documents or tell it to
continue. Instead, it works in small loops: build something, check it, fix what
the check finds, then continue.

The journey itself is written down. A **workflow shape** is a small YAML file
that lists the steps of a run — brainstorm, review the spec, plan, review the
plan, implement, review, deliver — and `fr-goal` reads that file rather than
containing the sequence in its own prose. Asking for `fr-goal` with no argument
runs the shape described in this article: feature delivery, test first. Naming
one, as in `fr-goal ux-research`, runs a different shape. A project can write
shapes of its own, or replace a shipped one by saving a file of the same name
in its own repository, without modifying the tool that runs them.

That autonomy begins with a hard physical boundary, and the boundary is
established before the first step of the shape runs — not by the run, but for
it. **`fr run start` creates the isolated workspace** — a separate Git worktree,
plus the project's development container — and only then writes down that a run
exists. Everything after that happens inside it. The original checkout is not
the place where autonomous work happens, and where containers are used, a
missing container profile stops the run rather than silently weakening this
guarantee.

A run also keeps a **durable record of its own progress**. A file on the feature
branch says which step the run is on, what each finished step produced, and
whether it is waiting on you. Without one, all of that would live in the
conversation and end with it: interrupt the run, and the thread is gone. With
one, you can ask where a run got to, pick it back up, or read afterwards — in
the pull request, next to the code — what happened in what order.

Verification also happens at two levels. **Acceptance tests** gather evidence
that the promised user-visible behavior works while the feature is being built.
For a deployed change, a separate **manual Test Plan** checks the result in the
real environment after merge. The agent does not merely leave that plan in the
pull request: it returns after the merge and walks the operator through it.

```mermaid
flowchart TD
    A[You describe the outcome] --> X[fr run start creates the workspace and the run record]
    X --> B[Agent studies the existing project inside it]
    B --> C[You answer one set of questions]
    C --> D[Agent writes the design and acceptance tests]
    D --> E[Agent breaks the work into small pieces]
    E --> F[Build the next piece]
    F --> G[Review it and run its tests]
    G --> H{Problems found?}
    H -->|Yes| I[Fix them]
    I --> G
    H -->|No| J{More pieces?}
    J -->|Yes| F
    J -->|No| K[Prepare the pull request]
    K --> L[You review and merge]
    L --> M[Agent confirms the change arrived]
    M --> N{Manual Test Plan?}
    N -->|Yes| O[Agent guides you through real-world checks]
    N -->|No| P[Close out the work]
    O --> P
```

This is autonomous work, not blind work. `fr-goal` stops when a choice belongs
to you, when an action needs human access, or when it encounters a blocker it
cannot safely resolve. It never interprets an unanswered question as consent
(`plugins/super-fr/skills/fr-goal/SKILL.md:16-36`). The reviews shown above are
agent-driven and disclosed in the pull request; you still perform the human
review and decide whether to merge.

## When it triggers

Use `fr-goal` when you know the outcome you want and want the agent to own the
delivery process, not merely suggest a design or edit one file. A useful request
states the outcome first and uses the remaining context for constraints that
are specific to this feature:

```text
/fr-goal Add import and export of saved dashboard filters.
Preserve existing filters, use a documented JSON format, and include migration tests.
```

The command itself already means "ask once, work autonomously, and take this to
a pull request," so repeating that contract wastes the most useful part of the
prompt. Add business rules, compatibility requirements, examples, or known
risks instead.

Because the pipeline is a shape, the command also takes an optional shape name.
`/fr-goal` runs the feature-delivery shape this article describes;
`/fr-goal <name>` runs another one that the project or the plugin provides
(`plugins/super-fr/skills/fr-goal/SKILL.md:16-29`). Most requests never need
the argument, and nothing about the rest of this article changes when you use
it: the machinery is the same, only the list of steps differs.

The skill also recognizes `/goal` and natural-language requests such as "build
this autonomously" or "take this to a PR"
(`plugins/super-fr/skills/fr-goal/SKILL.md:3-11`). Use interactive
`fr-brainstorming` instead when you want to shape the design together over
several conversations. `fr-goal` also requires the repository's isolated
development environment; if that has not been set up, it pauses and offers the
setup interview rather than working directly on your machine
(`plugins/super-fr/skills/fr-brainstorming/SKILL.md:23-44`).

## Workflow

The simple loop above is assembled from several narrower super-fr features, and
the assembly itself is a file you can open. Each feature solves a different
failure mode: damaging the original checkout, building the wrong thing, losing
track of unfinished work, hiding human-only steps, merging before review fixes
arrive, or cleaning up before the change is actually present. The two sections
below describe the file that orders those features and the record that tracks
them; the numbered sections after that introduce each feature at the point where
it joins the whole.

### The pipeline is a manifest, not a script

Here are two steps from the shape that runs when you ask for `fr-goal` with no
argument (`plugins/super-fr/workflows/fr-goal.yaml`):

```yaml
workflow: fr-goal
unit: run
requires: [git, tests, scm]

steps:
  - id: brainstorm
    kind: agent
    skill: super-fr:fr-brainstorming
    gate: operator
    emits: [spec, journal:spec]

  - id: plan-review
    kind: cli
    run: fr plan self-review {{ artifacts.plan }}
```

Three ideas in that fragment do most of the work.

**A step declares its kind.** `kind: cli` marks a deterministic command. `fr`
runs it directly and the exit code is the verdict — nothing interprets the
result, nothing negotiates with it. `kind: agent` marks judgment work, and
`fr` does not run those steps at all. It prints a brief saying which skill or
agent should do the work, what that work needs, and what it must produce; the
coding agent does the work; the outcome is then recorded back into the run.
That separation is deliberate rather than incidental. It keeps the engine a
plain program you can read, re-run, and get the same answer from, and it means
every unpredictable part of the pipeline happens on the far side of a clearly
marked handoff where a human can see it. There is no path through the engine
that could call a language model even by accident.

**A step can carry a gate.** `gate: operator` means the run stops there until a
person answers. The shipped shape declares exactly one such gate, on the
batched question round — the single operator touchpoint the pipeline promises.
An unanswered gate is a stop, not a timeout with a default.

**A step declares what it needs and what it emits.** Artifacts are named —
`spec`, `plan`, `pr` — so a later step can find the specification an earlier
step wrote, and so the tool can tell whether the inputs a step depends on
actually exist before anything is dispatched anywhere.

Shapes are looked up in one order: your repository's
`docs/superpowers/workflows/<name>.yaml` first, then the copy shipped with the
plugin. A repository file of the same name replaces the shipped shape whole.
There is no field-by-field merging, and that is a decision rather than an
omission: a list of steps that is half yours and half the plugin's fails in
ways that are very hard to see. `fr workflow check` validates a shape before
you rely on it: unique step ids, no cycles, every `needs` satisfiable, and only
capabilities drawn from a known list, so a typo is an error you see rather than
a step that quietly never runs
(`docs/superpowers/specs/2026-08-14-workflow-shapes-and-workitem-dispatch-design.md`,
section 4.A).

### The run keeps its place

Starting a run creates `docs/superpowers/runs/<run-id>.yaml` inside the isolated
workspace. It holds the shape's name, the branch, the **cursor** — the step the
run is currently on — and one record per step: pending, running, blocked on a
gate, done, or failed, along with the paths of whatever that step produced.

Five commands move it. `fr run start` begins a run; `fr run status` prints
where it is; `fr run advance` executes the step under the cursor if it is a
command, or prints the dispatch brief if it is agent work; `fr run resolve`
records how a dispatched step turned out and answers an operator gate; and
`fr run check` fails loudly when the cursor is sitting on a failed step.

Two details make this more than bookkeeping. First, a failed step **does not**
move the cursor. Success advances, failure stays put, so a stalled run keeps
reporting the same step until someone deals with it rather than sliding past it.
Second, the file is committed on the feature branch, not kept in a scratch
directory. That is why the run arrives in the pull request alongside the code:
a reviewer can see which steps ran, what each one emitted, and where the run
paused, without having been present for it. When the plan is archived after
merge, its run record is archived with it.

### 1. Establish the boundary before everything else (`fr run start`)

Before reading deeply, running measurements, asking design questions, or
changing code, `fr-goal` creates an **isolation** for this one goal. This is not
just a temporary folder. It combines two boundaries:

- A separate Git worktree holds the branch and file changes outside the
  original checkout.
- A devcontainer supplies the tools and runtime used to build and test those
  changes.

The worktree remains visible on the host, so the agent can edit it normally.
Builds, tests, and project commands cross an execution bridge into the
container. Authenticated Git and GitHub operations stay on the host, while the
container receives only the secrets explicitly assigned to its profile and no
SSH identity (`plugins/super-fr/skills/fr-isolation/SKILL.md:67-80`). On a host
with no container runtime the worktree is the isolation on its own, and the
project's container profile is not required.

Technically, this happens inside `fr run start`. It resolves the shape first —
so a mistyped shape name fails before any worktree or container is created —
then ensures the isolation for the branch, then writes the run's record inside
the resulting workspace. Every later command is run from there. A new feature
branch is normally based on the latest remote default branch
(`plugins/super-fr/skills/fr-brainstorming/SKILL.md:23-44`).

It is worth knowing why isolation is a precondition rather than the run's own
first step, because the alternative was tried and does not work. If entering
isolation were step one, the run's record would be written in the original
checkout and the worktree would be created afterwards — so the run could no
longer find itself from inside its own workspace, and a command like
`fr plan self-review` would look for a plan in the checkout where it does not
exist. A run recorded in the original checkout also misses the whole point of
recording it: it would not be on the feature branch, and would never reach the
pull request. A run is born in its workspace.

The same isolation persists through brainstorming, specification, planning,
implementation, review fixes, and pull-request delivery. There is no handoff to
a less protected workspace halfway through the run. An isolation marker,
tool-layer edit hook, and session-sentinel Bash guard also make accidental drift
back into the base checkout harder. These are discipline backstops with
documented escapes and fail-open cases, not a security boundary.

### 2. Explore first, then ask once (`brainstorm`)

The agent does not begin by asking questions it could answer from the project.
It first studies how the current system works and compares possible approaches.
Only then does it collect the decisions that genuinely belong to you into one
question set, with no more than four questions and recommended choices first.
A deployed change may include a question about how you will verify it in the
real environment (`plugins/super-fr/skills/fr-goal/SKILL.md:38-45`).

This is the shape's one operator gate, and an unanswered batch is a hard stop.
"Recommended" communicates judgment; it is not a timeout default. Straggling
decisions are batched rather than dripped out as repeated interruptions. When
you do answer, the step is closed by recording both the outcome and the path of
the specification it produced, which is how every later step knows where to
find that document. This is why "one operator touchpoint" describes the
expected path, not an unconditional promise of one conversation turn.

| Event | Pause? | Why |
|---|---:|---|
| Initial product and architecture decisions | Yes, once | These decisions belong to the operator. |
| Spec and plan approvals | No | Approval pauses become review-and-fix passes. |
| A valid code-review finding | No | The agent fixes it and tests the fix. |
| A factually incorrect finding | No | The agent records a reasoned refutation. |
| Missing access, profile, or required answer | Yes | Guessing would change scope or cross a boundary. |
| Secret, UI operation, or deployment | Yes | These become manual phases. |
| PR merge | Yes | The agent never self-merges. |
| Post-merge environment validation | Usually | It needs the deployed environment. |

### 3. Define how success will be proved (`spec-review` and acceptance tests)

Your answers become a **specification**, a document that says what will change
and why. The next step checks that document against both your answers and the
existing project. If it refers to a service, helper, or path that does not
exist, the discrepancy must be resolved before planning. The file lives at
`docs/superpowers/specs/<YYYY-MM-DD-slug>-design.md`
(`plugins/super-fr/skills/fr-goal/SKILL.md:47-53`).

The important promises also become **acceptance tests**: concrete statements of
what a user or operator must be able to do when the feature is complete. For
example, "a saved filter survives export and import" is acceptance; "a helper
returns a dictionary" is only an implementation detail.

super-fr records each promise as a row in its acceptance matrix. The row starts
as not implemented, identifies the intended verification level, and is linked
to the plan phase that will satisfy it. As implementation lands, `fr-goal`
updates the row with honest evidence such as a unit, integration, or end-to-end
test. This prevents completed code from being mistaken for proven behavior.
Under `fr-goal`, the agent presents these rows and a short defense for each
during the spec review rather than asking for another approval
(`plugins/super-fr/skills/fr-brainstorming/SKILL.md:67-76`,
`plugins/super-fr/skills/fr-plan/SKILL.md:79-84`).

Not every promise can be automated immediately. Any remaining acceptance debt
stays visible in the final pull request instead of being quietly described as
done (`plugins/super-fr/skills/fr-goal/SKILL.md:93-103`).

### 4. Turn the design into a checkable plan (`plan` and `plan-review`)

The specification says what success means; the plan says how to get there.
`fr-goal` invokes `fr-plan` to divide the work into phases and small steps. It
skips `fr-plan`'s usual section-by-section approval because the reviewed spec
already records your decisions. Each phase carries its own checklist, tests,
dependencies, and links to the acceptance criteria it advances
(`plugins/super-fr/skills/fr-plan/SKILL.md:15-38`,
`plugins/super-fr/skills/fr-plan/SKILL.md:63-84`).

Reviewing that plan is the shape's one command step, and a good illustration of
why the distinction between kinds matters. `fr plan self-review` runs against
the plan the previous step emitted, and its exit code decides whether the run
moves on; nobody has to judge whether the output "looks fine." The CLI errors on
defects such as dependency cycles and manual work hidden inside an agentic
phase; when a local Test Plan and readable acceptance matrix are present, it
also errors on unknown acceptance IDs, and it checks that a plan naming its own
workflow shape names one that actually resolves. It warns about unresolved
local spec references (`packages/fr/src/fr/plan_ops.py:867-1029`). The agent
fixes what it reports and advances the run again; there is nothing to record by
hand, because a command step completes itself.

### 5. Separate work only a human can do (manual phases)

Some work cannot safely be delegated: entering a secret, approving an account,
changing a setting in a web interface, or deploying into an environment only
you can access. The plan labels this as a **manual phase** rather than hiding it
inside an automated step. `fr-goal` then decides where that phase belongs:

```mermaid
flowchart TD
    A{Human-only work?} -->|No| B[Agentic phases only]
    A -->|Yes| C{Does later agentic work depend on it?}
    C -->|No| D[Back-load as final phase]
    D --> E[Operator completes it on the same PR]
    C -->|Yes| F[Front-load the manual phase]
    F --> G[Deliver reviewed spec and plan, then pause]
    G --> H[Resume after operator confirmation]
```

Back-loading is the default. The final PR labels the phase as unimplemented,
and the operator performs it and records a completion note on the same branch.
Front-loading is reserved for genuine prerequisites; then the manual
instructions are themselves the first deliverable
(`plugins/super-fr/skills/fr-goal/SKILL.md:55-63`).

### 6. Build, test, and review in a loop (`implement` and `review`)

Now the central loop from the opening diagram begins. The shape says this step
runs once per plan phase, so the phases are worked through in dependency order,
one at a time. Each one goes to a dedicated phase executor, which is given the
phase's scope, the specification, and the running journal of what earlier phases
discovered. It writes a failing test, implements the behavior, and cleans up
without changing that behavior. This test-first cycle is commonly called
**TDD**, or test-driven development.

The work stays in the original isolated workspace, so the design reasoning, the
plan, and your answers all remain in reach. The journal is what carries context
from one phase to the next: findings, decisions, and discoveries are written
down rather than being remembered, which is what makes a phase handover
survivable at all. Progress is recorded step by step, and acceptance rows are
updated only when there is honest test evidence
(`plugins/super-fr/skills/fr-goal/SKILL.md:70-84`,
`plugins/super-fr/skills/fr-execute/SKILL.md:79-82`).

At each completed phase, or after all implementation for a small plan, the
agent reviews the spec, plan, and code together. It fixes every valid finding
with tests. It may reject a finding only with explicit, factual reasoning;
silent dismissal is not allowed. Each finding is recorded as open, fixed, or
refuted, and that durable list — not anyone's memory of the review — is what
the pull-request description is later written from
(`plugins/super-fr/skills/fr-goal/SKILL.md:86-91`).

### 7. Keep delivery in draft until the checks pass (`deliver`)

The agent opens one **draft pull request**, a visible change that GitHub marks as
not ready to merge. It remains a draft while reviews and fixes continue. Only
after the full test suite and plan checks pass does `fr-goal` mark it ready for
your review (`plugins/super-fr/skills/fr-goal/SKILL.md:93-103`).

This ordering follows a recurring failure: implementers opened mergeable PRs
before orchestration review, operators merged them, and later fixes were pushed
to branches whose PRs were already closed. The draft state, a merged-PR push
guard, and post-merge content verification now protect that transition
(`docs/superpowers/implemented/specs/2026-06-20-fr-goal-merge-race-guard-design.md:34-159`).

The final PR discloses the spec and plan, review findings and fixes, refuted
findings, unfinished manual work, operator-driven Test Plan, and remaining
acceptance debt — and, because the run's record is committed on the same branch,
the sequence of steps that produced all of it. The agent then stops. Merge
remains the operator's decision.

### 8. Confirm the merge, then drive the manual Test Plan

When you report the merge, `fr-goal` checks that the final result actually
arrived on the project's main line before deleting its workspace. It runs
`fr isolation verify-merge`, freshly fetches the default branch, confirms the
PR state, and compares that content. This deliberately verifies results rather
than commit identity, so squash, rebase, and merge commits are supported. If a
late fix is missing, the workflow stops for a cherry-pick or fresh PR instead
of archiving incomplete work (`packages/fr/src/fr/commands/isolation_cmd.py:455-516`,
`packages/fr/src/fr/isolation/local.py:492-525`).

For a change that must be proven in a deployed environment, the specification
contains a **manual Test Plan** agreed during the initial question round. This
is different from the acceptance tests gathered during implementation: it may
require opening the real application, observing production behavior, checking
a dashboard, or performing an operation with access the isolated agent does not
have.

After merge verification, the agent drives this session interactively. It
presents the next check, asks the operator to perform or observe the human-only
part, records the result, and continues until the plan passes or a failure
requires recovery. It then reports any remaining acceptance debt, confirms plan
completion, archives the plan, its journal, and its run record through a
housekeeping PR, and tears down isolation or lets garbage collection reap it
(`plugins/super-fr/skills/fr-goal/SKILL.md:105-109`).

### When one goal spans several repositories

The delivery unit is still one repository: one workspace, one plan, one branch,
and one PR. A coordinating spec may cover several repositories, but `fr-goal`
locates each checkout and assigns one isolated agent per other repository, each
running this same pipeline from planning onward in its own repo. Dependencies
between repositories live in the spec and PR order, not in a plan phase's local
`depends_on` field (`plugins/super-fr/skills/fr-goal/SKILL.md:47-53`).

The shape decides the granularity at which its work is handed out, by declaring
one of three units: a whole run as a single item, which is what the shipped
shape does; one item per plan phase; or one item per target repository of a
cross-repo spec. Because the unit is declared in the manifest rather than fixed
in the tool, how finely a goal is divided is a property of the pipeline you
chose, not of the machine that happens to run it.

## Configuration

There is still no `fr-goal` settings screen or per-command configuration. It
takes the feature-specific intent from your request and gets the rest from the
project: its isolated development environment, specification folder, plan
folder, and acceptance criteria. The sequence is one of those project-supplied
inputs too: a repository that wants a different pipeline writes a shape, rather
than looking for a flag that bends this one.

| Input or boundary | Source | Effect |
|---|---|---|
| Goal and autonomy request | Operator prompt | Defines scope and activates the skill. |
| Workflow shape | `docs/superpowers/workflows/<name>.yaml`, else the shipped copy | Defines the steps, their kinds, gates, and dispatch granularity. |
| Run record | `docs/superpowers/runs/<run-id>.yaml` | Tracks the cursor, each step's outcome, and what it emitted. |
| Product decisions | One batched Q&A | Constrains the spec and all later work. |
| Devcontainer profile | `.devcontainer/<profile>/devcontainer.json` | Defines isolated execution. |
| Profile secrets | `~/.config/fr/secrets/<repo>/<profile>.env` | Exposes only configured runtime secrets. |
| Spec | `docs/superpowers/specs/` | Records design, acceptance tests, and optional manual Test Plan. |
| Acceptance matrix | `docs/acceptance/matrix.yaml` | Tracks each business promise and the evidence proving it. |
| Plan | `docs/superpowers/plans/<slug>/` | Defines phases, TDD steps, and acceptance-test links. |
| Model per phase tier | `~/.config/fr/models.yaml` | Chooses which model implements a phase of a given difficulty. |
| Manual-phase placement | Dependency on human action | Selects back-loaded continuation or front-loaded pause. |
| Repository topology | Local and cross-repo spec references | Produces one plan and PR per repository. |

The workflow is not one large program. The shape supplies the sequence, the
skill supplies the judgment each step needs, and smaller commands and safety
checks enforce the risky parts. They protect the original checkout, inspect the
plan, prevent remote work from starting before its instructions are available,
warn about pushes to closed pull requests, and compare the merged result. These
checks are guardrails with documented limits, not a security boundary.

Shapes and run records arrived in super-fr 4.0.0, which is worth knowing in two
narrow cases. A plan that names its own workflow shape cannot be read by an
older `fr` at all, so such a plan requires the new version rather than
degrading; plans that name none are unaffected. And if you have written your own
runner to execute work elsewhere, its interface now receives a single work item
rather than a plan-and-phase pair, which is what allows one runner to serve
shapes of different granularity.

## Try it yourself

Start in a repository that has been prepared for super-fr. State the outcome on
the first line, then use the second line for constraints that are unique to the
feature:

```text
/fr-goal Add import and export of saved dashboard filters.
Keep existing saved filters compatible, document the JSON format, and test round trips.
```

Expect this visible sequence:

1. The agent announces `fr-goal`, starts the run, and enters isolation before
   examining code.
2. It explores the implementation and asks one consolidated question set.
3. After your answers, it writes and reviews the spec without section approvals.
4. It creates the plan, and the plan self-review runs as a command whose exit
   code decides whether the run continues.
5. It implements the agentic phases with TDD, one phase at a time.
6. It opens a draft PR, fixes review findings, verifies, and marks the PR ready.
7. You complete any disclosed manual phase and merge the PR.
8. After you report the merge, it verifies the merged content.
9. When a manual Test Plan exists, it guides you through each real-world check.
10. It reports remaining acceptance debt and closes out the isolated workspace.

At any point you can ask `fr run status <run-id>` where the run has got to, and
after the fact the same record is in the pull request. If you leave a required
design question unanswered, the expected output is not a guessed
implementation. The agent should restate the open questions and wait. If a
manual prerequisite blocks later code, expect a reviewed spec-and-plan PR
followed by a pause. Those stops are not failures of autonomy; they are the
controls that keep autonomous execution from silently making operator
decisions.

For a compact inventory of surrounding skills and commands, run `fr skills`.
The canonical contract is `plugins/super-fr/skills/fr-goal/SKILL.md`, and the
shipped shape it drives is `plugins/super-fr/workflows/fr-goal.yaml`.
