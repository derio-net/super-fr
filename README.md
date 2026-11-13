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
present, installs for those too. Running it again updates. You also need `git`, `jq` and
`rsync` (the installer names any that is missing),
[superpowers](https://github.com/obra/superpowers), [uv](https://docs.astral.sh/uv/), and
your forge's CLI logged in (`gh` by default); Docker is used for the default isolation.
Release candidates, OpenCode, Hermes and the CLI-only route are on the
[install page](https://derio-net.github.io/super-fr/reference/install.html).

## Your first goal, in a minute

In any repo, start your agent and type:

```
/fr-goal add rate limiting to the webhook receiver
```

With the default, container-based isolation, the first run in a repo interviews you briefly
and scaffolds a devcontainer profile; a host without Docker skips that and isolates in a
worktree alone. Then it isolates, brainstorms and asks its question round, and runs spec,
plan, test-driven implementation and review on its own. You get one PR to read and merge.
After the merge, the run's last message gives you one command to start the close-out, which
archives the plan and removes the workspace.

To see what is going on while it works: `fr status` shows plans and phases, and
`fr isolation status` shows the workspaces.

## The skills

You mostly type `/fr-goal`; the others are called for you or are there when you want one on
its own. Each name links to the page that covers it.

<!-- generated:skills -->
| Skill | Plugin | What it is for |
|---|---|---|
| [`fr-acceptance`](https://derio-net.github.io/super-fr/fr-acceptance.html) | super-fr | Keep the acceptance matrix honest; add rows, move statuses as evidence lands, backfill an existing repo. |
| [`fr-audit`](https://derio-net.github.io/super-fr/fr-audit.html) | super-fr | Show what a run or session cost and where the money went, and compare runs before and after a change. |
| [`fr-brainstorming`](https://derio-net.github.io/super-fr/fr-brainstorming-and-plan.html) | super-fr | Design a feature into a written spec, inside an isolated workspace from the first command. |
| [`fr-debugging`](https://derio-net.github.io/super-fr/fr-debugging.html) | super-fr | Find a bug's root cause in an isolated workspace and deliver the fix as a reviewed PR. |
| [`fr-devops-gate`](https://derio-net.github.io/super-fr/fr-devops-gate.html) | super-fr | Apply a delivered PR's manual operations (deploys, secrets, checks), record each result, then merge. |
| [`fr-dispatch`](https://derio-net.github.io/super-fr/fr-dispatch.html) | super-fr-dispatch | Queue a plan's phases to an autonomous runner and keep its tracking issues in step. |
| [`fr-execute`](https://derio-net.github.io/super-fr/fr-brainstorming-and-plan.html) | super-fr | Implement one phase of a plan, test-first, then stop. |
| [`fr-goal`](https://derio-net.github.io/super-fr/01-fr-goal.html) | super-fr | Take a feature from a sentence to a reviewed pull request, with one question round and no other approval gates. |
| [`fr-init`](https://derio-net.github.io/super-fr/fr-init.html) | super-fr | Interview you about a repo once and scaffold the devcontainer profiles its isolated runs use. |
| [`fr-isolation`](https://derio-net.github.io/super-fr/fr-isolation.html) | super-fr | Run work in a throwaway worktree and container so your checkout is never touched. |
| [`fr-origins`](https://derio-net.github.io/super-fr/fr-triage.html) | super-fr | Classify where a repo's recent bugs came from and which process change would have prevented them. |
| [`fr-plan`](https://derio-net.github.io/super-fr/fr-brainstorming-and-plan.html) | super-fr | Turn a spec into a phase-by-phase plan that tooling can track and an agent can execute. |
| [`fr-progress`](https://derio-net.github.io/super-fr/fr-progress.html) | super-fr | Report what is in progress, what drifted and what is ready to archive. |
| [`fr-runner`](https://derio-net.github.io/super-fr/fr-dispatch.html) | super-fr-dispatch | Check that an autonomous runner is alive and diagnose phases it did not pick up. |
| [`fr-triage`](https://derio-net.github.io/super-fr/fr-triage.html) | super-fr | Rank a repo's or an org's open issues, group them into batches and drive the batches to merged PRs. |
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
| `fr push` | Push this run's feature branch under the repo's git policy. |
| `fr skills` | Show the CLI surface and a summary of each skill. |
| `fr services` | Read-only: the resolved forge / ci / tracking services. |
| `fr acceptance` | Acceptance matrix: business-level acceptance tests × verification levels. |
| `fr plan` | Create, edit, review and rework plans. |
| `fr spec` | Spec status: which specs are planned, in progress or shipped. |
| `fr migrate` | Migrations: bring plans, layouts and artifacts up to this fr (preview by default). |
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
| `fr settings` | Per-repo feature settings: init, show, check. |
| `fr docs` | Docs currency: pages must keep up with the code they cover (read-only). |
| `fr lenses` | Review lenses: the angles a feature is reviewed from (read-only). |
| `fr gate` | Post-merge gates: record that a gate passed on its PR (the gate ledger). |
| `fr ops` | Manual operations of a plan: check, apply, attest. |
| `fr release` | Release gating: what still waits on a post-merge gate since the last final. |
| `fr closeout` | Close-out records: one outcome per spec Test Plan step. |
| `fr pr` | Pull requests fr opens (always drafts). |
<!-- /generated:cli -->

## Read more

The site: **https://derio-net.github.io/super-fr/**

- **Start here:** [the pipeline and why it is trustworthy](https://derio-net.github.io/super-fr/why-fr.html),
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

## Viewing the acceptance report

The report is derived from the acceptance fragments and never committed. Render it on your
machine with `fr acceptance report --open` (it writes the git-ignored
`docs/acceptance/report.html`; `--format md` writes Markdown). CI shows it on every pull
request as a job summary, and the published copy is at
**https://derio-net.github.io/super-fr/acceptance/**.

## Contributing

Working on super-fr itself: [`AGENTS.md`](AGENTS.md) covers the workflow, the release and
version rule, and the CI gate. The site is rebuilt from `docs/explainers/`, `docs/*.md` and
`docs/reference/` whenever a merge to `main` changes them.
