---
title: "fr: agent work you can merge"
tldr: |
  fr turns one goal into one reviewed pull request. The agent works in an isolated
  workspace, a separate reviewer checks each stage, and you keep the merge and every
  step that should not be automated.
standalone: true
standalone_style: broadsheet
layout: landing
hero:
  eyebrow: "super-fr"
  headline: "Give an agent a goal. Merge a PR you trust."
  subline: "fr turns one goal into one reviewed pull request, built in an isolated workspace and checked by a separate reviewer at every stage. You answer one question round up front, and the merge stays yours."
  command: "/fr-goal add rate limiting to the webhook receiver"
  primary: {label: "See how a run works", href: "01-fr-goal.md"}
  secondary:
    - {label: "Install", href: "../reference/install.md"}
    - {label: "GitHub", href: "https://github.com/derio-net/super-fr"}
facts:
  - {figure: "1", caption: "question round before the build, rarely two"}
  - {figure: "1", caption: "pull request per goal"}
  - {figure: "0", caption: "self-merges: you merge"}
  - {figure: "3", caption: "harnesses: Claude Code, OpenCode and Hermes"}
covers:
  - plugins/super-fr/skills/fr-goal/SKILL.md
  - plugins/super-fr/workflows/fr-goal.yaml
reviewed: 2026-11-12 rewritten as the landing front page
---

## How a run goes
<!-- landing:flow -->

1. **Isolate.** The run moves into a private workspace before anything is written.
2. {you} **One question round.** You answer the design questions once, and the agent commits to a written spec.
3. **Spec, then plan.** Both are reviewed before any code exists.
4. **Build test-first.** One phase at a time, with a review inside every phase.
5. **Review at every stage.** A separate reviewer reads the spec, the plan and each slice.
6. **One pull request.** The agent delivers it and never merges it.
7. {you} **The manual phase.** Secrets, deploys and other risky steps are done by you, with the agent guiding.
8. {you} **Merge, then the Test Plan.** You merge, then confirm what the agent cannot reach.

## The agent cannot touch what it should not
<!-- landing:guarantee -->

> An agent with write access to your checkout can collide with your in-flight work, and the commands it generates run with your credentials.

**What you gain.** Your clone is never touched, and the agent only holds what its workspace was explicitly granted.

**How.** Every run happens in a private git worktree outside your clone. By default its commands run in a sealed container with scoped credentials. A hook checks every edit against a marker in the workspace and refuses an edit to your clone before it reaches disk. Two docker-less modes keep the worktree and drop the container.

[How isolation works](fr-isolation.md)

## It asks you once, then builds from a written spec
<!-- landing:guarantee -->

> You hand an agent a sentence and it starts coding. Whether it built what you meant is luck.

**What you gain.** Your intent is pinned down before the build, so nothing downstream has to guess it.

**How.**

- You answer one question round sized to the feature. A second follows only when announced up front or when you ask, and there is never a third.
- The result is a spec with numbered requirements, then a plan cut into phases whose steps have ids, so progress is a fact on disk.
- The brainstorm also asks how the change will be proven before merge.

[From an idea to a plan](fr-brainstorming-and-plan.md)

## A separate reviewer reads the work, at every stage
<!-- landing:guarantee -->

> An agent that grades its own work will pass it.

**What you gain.** Findings are caught while they are cheap, and a review you can trust is one the author did not write.

**How.**

- The spec, the plan and every implementation slice are reviewed before the work moves on.
- A phase's review has to name the separate reviewer that did it, never the agent that wrote the code.
- Delivery has to name a test run the orchestrator ran itself. A finding the change caused is fixed; one it did not cause is filed and listed in the PR for you.

[How a run works, step by step](01-fr-goal.md)

## Proof that stays honest: the acceptance matrix
<!-- landing:guarantee -->

> A green test suite can sit on top of a product that does not do what anyone asked.

**What you gain.** A list of what a person can do with the product, and an honest read of how well each claim is proven.

**How.** Each row of the matrix is one business-level claim with the tests that verify it. Its status runs from automated, through proven live, to not yet implemented and known failing, and it moves only with a recorded reason. CI exits non-zero on a failing row, and where a claim sits between automated and unwired the rule is to choose unwired.

[The acceptance matrix](fr-acceptance.md)

## One pull request, never self-merged; the risky step stays yours
<!-- landing:guarantee -->

> Some steps should not be automated: creating a key, rotating a token, restarting a service.

**What you gain.** A pull request you review and merge, and a record of the operations around it instead of a note in a description.

**How.**

- The agent delivers the pull request and never merges it.
- Each manual operation becomes a typed record with a probe that says whether it is done.
- One command, `fr ops gate`, sequences those operations around the merge at your terminal. It refuses non-interactive contexts, so a delivering agent cannot run it, and it resumes at the first stage not yet recorded.

[The DevOps gate](fr-devops-gate.md)

## A trail you can read afterwards, with its cost
<!-- landing:guarantee -->

> When a run is done, can you say what it did and what it cost?

**What you gain.** Where the money went, from the harness's own records, and a way to tell whether a process change made runs cheaper.

**How.** `fr usage` reads what the harness recorded and takes the dollar figure it reports. It splits that across what the session was doing and which step it was in, and never prices a token itself. A figure nobody could observe prints as a dash, not as zero. `fr usage compare` sets two groups of runs side by side.

[Auditing a run's cost](fr-audit.md)

## From one goal to a backlog
<!-- landing:guarantee -->

> A single goal is easy to hand over. A whole backlog of issues is not.

**What you gain.** Judgements about the backlog that survive between runs, and a group of related issues shipped as one reviewed pull request.

**How.** `fr triage` keeps your judgements in a file that the engine reads and writes around, so a re-run costs only what is new. A batch is a group of judged issues delivered as one fr-goal run and one pull request.

[Ranking a backlog with fr-triage](fr-triage.md)

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
