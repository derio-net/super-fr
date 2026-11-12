---
title: "fr: agent work you can merge"
tldr: |
  fr turns one goal into one reviewed pull request. The agent works in an isolated
  workspace, a separate reviewer checks each stage, and you keep the merge and every
  step that should not be automated. The same pipeline then scales to a backlog, with
  exit gates that hold the final release and a driver that runs batches in waves.
standalone: true
standalone_style: broadsheet
layout: landing
hero:
  eyebrow: "super-fr"
  headline: "Give an agent a goal. Merge a PR you trust."
  subline: "fr turns one goal into one reviewed pull request, built in an isolated workspace and checked by a separate reviewer at every stage. You answer one question round up front, and the merge stays yours. Then it carries a whole backlog through gates and waves."
  command: "/fr-goal add rate limiting to the webhook receiver"
  terminal:
    - {kind: prompt, text: "/fr-goal add rate limiting to the webhook receiver"}
    - {kind: out, text: "workspace ready: private worktree, sealed container"}
    - {kind: you, text: "answer the design questions, once"}
    - {kind: out, text: "spec and plan written, both reviewed"}
    - {kind: out, text: "phases built test-first, each one reviewed"}
    - {kind: ok, text: "pull request delivered, not merged"}
    - {kind: you, text: "you merge, then walk the Test Plan"}
  primary: {label: "See how a run works", href: "01-fr-goal.md"}
  secondary:
    - {label: "Install", href: "../reference/install.md"}
    - {label: "GitHub", href: "https://github.com/derio-net/super-fr"}
facts:
  - {figure: "1", caption: "question round before the build, rarely two"}
  - {figure: "1", caption: "pull request per goal"}
  - {figure: "0", caption: "self-merges: you merge"}
  - {figure: "2", caption: "post-merge gates that hold the final release until you pass them"}
covers:
  - plugins/super-fr/skills/fr-goal/SKILL.md
  - plugins/super-fr/workflows/fr-goal.yaml
  - plugins/super-fr/skills/fr-isolation/SKILL.md
  - packages/fr/src/fr/verification/exit.py
  - packages/fr/src/fr/commands/gate_cmd.py
  - packages/fr/src/fr/triage/batch_drive.py
  - scripts/release.py
reviewed: 2026-11-12 second pass, two acts with exit gates and the wave driver added, each section checked against the page it links
---

## How a run goes
<!-- landing:flow -->

<!-- site:figure run-pipeline -->

1. **Isolate.** The run moves into a private workspace before anything is written.
2. {you} **One question round.** You answer the design questions once, and the agent commits to a written spec.
3. **Spec, then plan.** Both are reviewed before any code exists.
4. **Build test-first.** One phase at a time, with a review inside every phase.
5. **Review at every stage.** A separate reviewer reads the spec, the plan and each slice.
6. **One pull request.** The agent delivers it and never merges it.
7. {you} **The manual phase.** Secrets, deploys and other risky steps are done by you, with the agent guiding.
8. {you} **Merge, then the Test Plan.** You merge, then confirm what the agent cannot reach.

## One goal, one pull request you can trust
<!-- landing:act -->

Start with a single goal. Each of the four sections below is one reason the pull request at the end is worth your review.

## The agent cannot touch what it should not
<!-- landing:guarantee -->

> An agent with write access to your checkout can collide with your in-flight work, and the commands it generates run with your credentials.

**What you gain.** Your clone is never touched, and the agent only holds what its workspace was explicitly granted.

**How.** Every run happens in a private git worktree outside your clone, and by default its commands run in a sealed container with scoped credentials. A hook checks every edit against a marker in the workspace and refuses one aimed at your clone before it reaches disk.

<!-- site:figure isolation-boundary -->

[How isolation works](fr-isolation.md)

## It asks you once, then builds from a written spec
<!-- landing:guarantee -->

> You hand an agent a sentence and it starts coding. Whether it built what you meant is luck.

**What you gain.** Your intent is pinned down before the build, so nothing downstream has to guess it.

**How.** You answer one question round sized to the feature, and a second follows only when announced up front or when you ask. The result is a spec with numbered requirements, then a plan cut into phases whose steps have ids, so progress is a fact on disk.

[From an idea to a plan](fr-brainstorming-and-plan.md)

## A separate reviewer reads the work, at every stage
<!-- landing:guarantee -->

> An agent that grades its own work will pass it.

**What you gain.** Findings are caught while they are cheap, and a review you can trust is one the author did not write.

**How.**

- The spec, the plan and every implementation slice are reviewed before the work moves on.
- A phase's review has to name the separate reviewer that did it, never the agent that wrote the code.

[How a run is reviewed](01-fr-goal.md)

## One pull request, never self-merged
<!-- landing:guarantee -->

> Some steps should not be automated: creating a key, rotating a token, restarting a service.

**What you gain.** A pull request you review and merge, with the risky steps and the final check left in your hands.

**How.**

- The agent delivers the pull request and never merges it.
- Delivery has to name a test run the orchestrator ran itself. A finding the change caused is fixed; one it did not cause is filed and listed in the pull request for you.
- After the merge the agent can guide you through the manual Test Plan in the real environment.

[How a run is delivered](01-fr-goal.md)

## A whole backlog, run in waves
<!-- landing:act -->

Merging is not the end of the work, and one goal is not a backlog. These two sections cover what holds a release after the merge, and how many goals run at once.

## Merged is not done: the exit gates
<!-- landing:guarantee -->

> A green pull request cannot prove that the release installs on a clean machine, that a feature works against the real service, or that a secret was rotated.

**What you gain.** The work that cannot finish in the pull request is written on the merged pull request, and the final release waits for a person to pass it.

**How.**

- A run's spec names the gate that applies, Tester or DevOps, and the merged pull request carries it as a label.
- While a gate is held, merges to main cut only release candidates. The final release is cut once none is held.
- You pass a gate by walking its rows, or with `fr gate pass`.

<!-- site:figure gate-ledger -->

[How exit gates work](fr-exit-gates.md)

## A backlog, run in waves
<!-- landing:guarantee -->

> A single goal is easy to hand over. A backlog of twenty issues is a pile of bookkeeping.

**What you gain.** A ranked backlog becomes batches that each end in one pull request, run in waves that stop at a cap, and merged only when you approved them.

**How.**

- `fr triage` ranks the issues and groups related ones into batches, and each batch is one fr-goal run.
- `fr triage batch drive` dispatches the batches in waves, with at most four in flight by default.
- It merges a green batch pull request only once you label it `approved-fr`, and it keeps no state of its own, so you can stop it and start it again.

<!-- site:figure wave-of-batches -->

[The wave driver](fr-wave-driver.md)

## Also included
<!-- landing:grid -->

Smaller pieces of the same pipeline, each with its own page.

- **The acceptance matrix.** A list of what a person can do with the product, with an honest read of how well each claim is proven. [How claims are proven](fr-acceptance.md)
- **The cost audit.** Reads what the harness recorded and splits the money across activities and steps, without ever pricing a token by hand. [Auditing a run's cost](fr-audit.md)
- **Debugging.** Finds the cause first, in an isolated workspace, and delivers the fix as a reviewed pull request that pins the bug with a failing test. [Debugging with fr](fr-debugging.md)
- **The triage board.** Keeps your judgements about a backlog in a file, so a re-run costs only what is new. [Ranking a backlog](fr-triage.md)
- **The DevOps gate.** Each manual operation is a typed record with a probe, sequenced around the merge by `fr ops gate` at your terminal. [The DevOps gate](fr-devops-gate.md)
- **Three harnesses.** One command installs the CLI and the plugins for Claude Code, and the skills too where OpenCode or Hermes Agent is present. [Install](../reference/install.md)

## The long read
<!-- landing:prose -->

If you want the whole argument in one page, [why fr is built around trust](why-fr.md) walks through the pipeline and the five properties each guarantee buys.

## Every page
<!-- landing:pages -->

The [acceptance report](./acceptance/) lists every business-level promise and how it is proven.

<!-- site:pages -->

## Try it
<!-- landing:cta -->

In any repo, this is the entry point to everything above. fr sets up the isolated workspace itself the first time.

`/fr-goal add rate limiting to the webhook receiver`

[See how a run works](01-fr-goal.md) [Install](../reference/install.md)
