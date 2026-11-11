# super-fr

[![GitHub Release](https://badgen.net/github/release/derio-net/super-fr/stable)](https://github.com/derio-net/super-fr/releases)
[![CI](https://github.com/derio-net/super-fr/actions/workflows/ci.yml/badge.svg)](https://github.com/derio-net/super-fr/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Acceptance](https://img.shields.io/badge/acceptance-report-blue)](https://derio-net.github.io/super-fr/acceptance/)

**Describe a feature, get back a reviewed pull request.** Tell super-fr what you want,
answer a question round sized to the feature (rarely two), and an agent designs it, writes
it test-first, reviews its own work and opens a single PR for you to merge. It does all of
that in an isolated workspace, so your checkout is never touched.

It is for people who already use an AI coding agent and want its output to be something they
can merge: planned before it is built, tested as it is built, and reviewed before you see it.
super-fr is two [Claude Code](https://claude.com/claude-code) plugins plus a command-line
tool, `fr`. They build on [superpowers](https://github.com/obra/superpowers) and also run on
OpenCode 2.x and Hermes Agent.

Full documentation: **https://derio-net.github.io/super-fr/**

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/derio-net/super-fr/main/scripts/bootstrap.sh | bash
```

This installs the `fr` CLI, enables the Claude Code plugins and, if OpenCode or Hermes is
present, installs for those too. Running it again updates. You also need
[superpowers](https://github.com/obra/superpowers), [uv](https://docs.astral.sh/uv/), and
your forge's CLI logged in (`gh` by default); Docker is used for the default isolation.
Release candidates, OpenCode, Hermes and the CLI-only route are on the
[install page](https://derio-net.github.io/super-fr/reference/install.html).

## Your first goal, in a minute

In any repo, start your agent and type:

```
/fr-goal add rate limiting to the webhook receiver
```

The first time in a repo, super-fr scaffolds a devcontainer profile after a short interview.
Then it isolates, brainstorms and asks its question round, and runs
spec, plan, test-driven implementation and review on its own. You get one PR to read and
merge. When it is merged, `fr archive` and `fr isolation down` close the run out.

To see what is going on while it works: `fr status` shows plans and phases, and
`fr isolation status` shows the workspaces.

## The skills

You mostly type `/fr-goal`; the others are called for you or are there when you want one on
its own. A page for each is listed under [Read more](#read-more).

<!-- generated:skills -->
| Skill | Plugin | What it is for |
|---|---|---|
| `fr-acceptance` | super-fr | Drive the acceptance matrix: backfill an existing repo's business-level acceptance tests into docs/acceptance/matrix.yaml… |
| `fr-audit` | super-fr | Use when asked what a run or session cost, where the money went, whether a process change made the pipeline cheaper… |
| `fr-brainstorming` | super-fr | Brainstorm a feature INSIDE an isolated workspace: invokes fr-isolation first… |
| `fr-debugging` | super-fr | Debug a bug, test failure, or unexpected behavior INSIDE an isolated workspace and deliver a reviewed fix-PR. |
| `fr-devops-gate` | super-fr | Use when a delivered run's effective gates include devops, when `fr pickup --run` prints a DevOps brief… |
| `fr-dispatch` | super-fr-dispatch | Queue a plan's phases to a runner (`fr apply --to <runner>`) and reconcile its GitHub Issues. |
| `fr-execute` | super-fr | Execute an agentic phase from a plan. |
| `fr-goal` | super-fr | Run a feature goal end-to-end autonomously via the `fr-goal` workflow shape: brainstorm, one question round sized to the feature… |
| `fr-init` | super-fr | Initialize a repo for isolated runs: scan it, interview the operator about working patterns, tools, and credentials… |
| `fr-isolation` | super-fr | Run work in an isolated workspace: git worktree + devcontainer, driven through the `fr isolation` CLI (exec-bridge). |
| `fr-origins` | super-fr | Use when asked where a repo's recent bugs came from, to classify the issues filed in a window by origin, to build a defect-origins page… |
| `fr-plan` | super-fr | Write phase-structured plans with operator collaboration. |
| `fr-progress` | super-fr | Plan / spec progress reporting, and the repo-state preflight for any repo with docs/superpowers/ or fr config. |
| `fr-runner` | super-fr-dispatch | Operate and debug an autonomous runner: verify tick health, diagnose stuck or undispatched phases, recover orphan workspaces… |
| `fr-triage` | super-fr | Use when asked to triage, rank, prioritise or organise the open issues of a repo or of a whole org… |
<!-- /generated:skills -->

## The `fr` command line

The skills drive `fr`, and every step they take is a command you can run yourself. Add
`--help` to any of these. The full tree with every subcommand is on the
[CLI page](https://derio-net.github.io/super-fr/reference/cli.html).

<!-- generated:cli -->
| Command | What it does |
|---|---|
| `fr apply` | Render + observe + diff + apply for a plan. |
| `fr status` | Read-only plan report (allowlist-safe; never mutates). |
| `fr archive` | Move finished plans (and specs) to implemented/. |
| `fr undispatch` | Close a plan's tracking Issues and null the fields. |
| `fr pickup` | Output phase scope (markdown) for an agent. |
| `fr repair` | Normalize stale plan/spec refs + strip dead plan-config keys (dry-run; --yes to write). |
| `fr skills` | Show the v2 CLI surface + skill summaries. |
| `fr services` | Read-only: the resolved forge / ci / tracking services. |
| `fr acceptance` | Acceptance matrix: business-level acceptance tests × verification levels. |
| `fr plan` | v2 plan editing commands. |
| `fr spec` | v2 spec status commands. |
| `fr migrate` | v2 migration tools. |
| `fr isolation` | Isolated workspaces: git worktree + devcontainer. |
| `fr init` | Repo initialization: devcontainer profile scaffolding (driven by fr-init). |
| `fr cloud` | Claude Code cloud sessions: check the environment, print its setup script. |
| `fr repos` | Instrument locally-checked-out repos (driven by the operator's collection). |
| `fr journal` | Scope-keyed durable run-state (spec\|plan\|debug): add / render / check. |
| `fr models` | Tier→model bindings for fr-goal subagent dispatch (harness-keyed). |
| `fr harness` | Declared harness-parity matrix: which surfaces are wired on which harness. |
| `fr hermes` | Install/uninstall super-fr into a Hermes Agent home. |
| `fr workflow` | Workflow shape manifests: resolve (repo > shipped) and validate. |
| `fr verification` | Verification strategies: resolve (repo > shipped) and validate. |
| `fr run` | Durable workflow-run cursor: start / status / advance / resolve / check. |
| `fr validate` | Structural validation of generated artifacts. |
| `fr triage` | Backlog triage: collect forge facts, check judgements, render a board. |
| `fr usage` | What harness sessions and runs cost, split by activity and step (read-only). |
| `fr debt` | What this repo owes: acceptance, plans and owed actions (read-only). |
| `fr docs` | Docs currency: pages must keep up with the code they cover (read-only). |
| `fr gate` | Post-merge gates: record that a gate passed on its PR (the gate ledger). |
| `fr ops` | Manual operations: check, apply, attest (spec 2026-10-22-fr-ops). |
| `fr release` | Release gating: what still waits on a post-merge gate since the last final. |
| `fr closeout` | Close-out records: one outcome per spec Test Plan step. |
<!-- /generated:cli -->

## Read more

The site: **https://derio-net.github.io/super-fr/**

- **Start here:** [the pipeline and why it is trustworthy](https://derio-net.github.io/super-fr/index.html),
  [`/fr-goal`](https://derio-net.github.io/super-fr/01-fr-goal.html),
  [isolation](https://derio-net.github.io/super-fr/fr-isolation.html),
  [from idea to plan](https://derio-net.github.io/super-fr/fr-brainstorming-and-plan.html),
  [dispatching phases to a runner](https://derio-net.github.io/super-fr/fr-dispatch.html).
- **Skill pages:** [debugging](https://derio-net.github.io/super-fr/fr-debugging.html),
  [acceptance](https://derio-net.github.io/super-fr/fr-acceptance.html),
  [progress](https://derio-net.github.io/super-fr/fr-progress.html),
  [init](https://derio-net.github.io/super-fr/fr-init.html),
  [triage](https://derio-net.github.io/super-fr/fr-triage.html),
  [audit](https://derio-net.github.io/super-fr/fr-audit.html),
  [DevOps gate](https://derio-net.github.io/super-fr/fr-devops-gate.html).
- **Guides:** [docs currency](https://derio-net.github.io/super-fr/guides/docs-currency.html),
  [verification strategies](https://derio-net.github.io/super-fr/guides/verification-strategies.html),
  [manual operations](https://derio-net.github.io/super-fr/guides/ops.html),
  [cloud setup](https://derio-net.github.io/super-fr/guides/cloud-setup.html),
  [herdr control sessions](https://derio-net.github.io/super-fr/guides/herdr-control-sessions.html),
  [merge protection](https://derio-net.github.io/super-fr/guides/merge-protection.html),
  [gate backfill](https://derio-net.github.io/super-fr/guides/gate-backfill.html),
  [the release walk](https://derio-net.github.io/super-fr/guides/exit-gates-release-walk.html).
- **Reference:** [install](https://derio-net.github.io/super-fr/reference/install.html),
  [CLI](https://derio-net.github.io/super-fr/reference/cli.html),
  [plan model](https://derio-net.github.io/super-fr/reference/plan-model.html),
  [workflow shapes](https://derio-net.github.io/super-fr/reference/workflow-shapes.html),
  [dispatch labels](https://derio-net.github.io/super-fr/reference/dispatch-lifecycle.html),
  [acceptance matrix](https://derio-net.github.io/super-fr/reference/acceptance-matrix.html),
  [Hermes](https://derio-net.github.io/super-fr/reference/hermes.html),
  [components and requirements](https://derio-net.github.io/super-fr/reference/components.html).

## Contributing

Working on super-fr itself: [`AGENTS.md`](AGENTS.md) covers the workflow, the release and
version rule, and the CI gate. Pages under `docs/` are published by every merge to `main`.
