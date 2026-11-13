---
title: "Verification strategies"
tldr: |
  A verification strategy says how a change is proven before or after it merges. This page is for the person who writes a strategy, or makes a repo usable by one.
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/verification/**
reviewed: 2026-11-13 placement emitted paths fix, run/ops/pickup/verification readers now resolve a run's emitted spec and plan below the artifact root; nothing this page describes changed
---

# Verification strategies

A verification strategy says how a change is proven before (or after) it merges.
A run's spec names one in its `## Verification` section. `fr verification walk`
runs the pre-merge ones. `deliver` does not finish a run whose walk is owed
and not there. This page is for the person who writes a strategy, or makes a repo
usable by one.

## The four that ship

| Strategy | When | Driver | Source | What it does |
|---|---|---|---|---|
| `candidate` | pre-merge | agent | the PR's worktree | installs the PR's build into a throwaway prefix, runs each row's scenario in a fresh fixture repo |
| `client-live` | pre-merge | operator | the PR's worktree | the same install; the operator drives the scenario inside a real client repo (`--client <path>`) |
| `prerelease` | pre-merge | operator | an on-demand rc tag | installs from `fr verification prerelease --branch <b>`'s output. `fr verification walk` does not run it (it never runs a `source: prerelease` strategy). The PR body prints a manual route for each row instead |
| `live` | post-merge | operator | none | the released build, run by the operator after merge |

`fr verification list` shows every strategy that resolves and where each came
from; `fr verification check <name>` (or `--all`) validates manifests.

## Resolution order

A strategy name resolves in this order, and the first hit wins. A repo file replaces a
shipped one wholesale (fields are not merged):

1. `docs/superpowers/verifications/<name>.yaml` in the repo;
2. `$FR_SHIPPED_VERIFICATIONS_DIR/<name>.yaml`, an explicit escape;
3. the manifests inside the `fr` wheel;
4. the plugin clone's `plugins/super-fr/verifications/<name>.yaml`.

fr does not accept a manifest whose `verification:` does not match its file name. The
word `none` is reserved. It is not a strategy: it marks a row verified some
other way.

## Write a strategy

A manifest is one YAML file:

```yaml
verification: <name>        # must equal the file name; never `none`
schema: 1
description: one line
when: pre-merge             # or post-merge
driver: agent               # agent: the walk runs it; operator: a human drives it
install: <argv or null>     # how to install the build, see below
scenario: <argv or null>    # how to run one row's scenario
source: worktree            # worktree | prerelease | none
gate: tester                # schema 2 only: none | tester | devops (default none)
notes: free text
```

`schema: 2` is the version that may carry `gate:`, the strategy's default
post-merge gate. The gate says who must act on a run that uses the strategy, once the run
has merged. A schema 1 manifest with a `gate:` is not accepted, and an absent `gate:`
means `none`. The shipped `live` is schema 2 with `gate: tester`; the others stay schema 1.

A repo can remap a kind's gate in `.fr/triage.yaml` (`exit: {gates: {<kind>:
<gate>}}`). A spec's `## Verification` section can set the run's gate with
`gate: <gate>`, and one row's gate with `gate: <row-id>=<gate>`. `fr verification exit
--run <id> | --spec <path>` prints the kinds, gates and gated rows that result.

The repo's settings (`fr settings show`) can switch this off. Under
`artifacts.gates: off`, no gate is computed, labelled or held. A spec whose
`## Verification` still sets `gate:` is then not accepted when its `brainstorm` or
`spec-review` step resolves, and `fr validate artifacts` fails it too. Under
`artifacts.test_plan: off`, a spec that has a `## Test Plan` is not accepted at the same
points, and close-out owes no Test Plan outcomes. Strategies and walks still run. The PR's
`verification:*` and `gate:*` labels follow `forge.labels` alone.

`install` and `scenario` are a string (split like a shell would) or a list of
strings. They may interpolate these placeholders and no others:

| Placeholder | Value |
|---|---|
| `{repo}`, `{worktree}`, `{source}` | the checkout being verified (for `prerelease`, the rc source) |
| `{prefix}` | a fresh temporary directory outside the repo; everything the install creates goes here |
| `{bin}` | `<prefix>/bin`, put first on `PATH` for every step |
| `{fixture}` | a fresh `git init` repo; each row's scenario runs in a copy of it |
| `{client}` | the `--client` repo, else the fixture |
| `{scenario}` | the row's `scenario:` script, repo-relative in its acceptance fragment |

`fr verification check` fails these:

- a post-merge strategy that installs anything (the released build is what runs);
- an agent-driven pre-merge strategy with no `scenario` template;
- a `{source}` placeholder when `source:` is `none`.

A row on an agent-driven pre-merge strategy also needs a `scenario:` on its matrix row.
`fr plan self-review` and `deliver` do not accept one without it.

### Example: a `staging` strategy

This strategy checks the PR's build against a staging backend, and an operator drives it.
The install comes from the PR's worktree build (`{worktree}`), so the manifest sets
`source: worktree`. A manifest that omits `source:` gets `none`. The walk still needs a
`scenario:` on every row that it covers. It runs that scenario after the install and smoke,
so the scenario is what reaches staging. The operator gives the client wired to staging
with `--client`:

```yaml
# docs/superpowers/verifications/staging.yaml
verification: staging
schema: 1
description: Install the PR's worktree build, then run each row's scenario in a client wired to staging.
when: pre-merge
driver: operator
install: .fr/candidate-install {prefix} {worktree}
scenario: "{scenario}"
source: worktree
notes: Run with --client pointing at a checkout wired to staging; every covered row needs a scenario.
```

Then `fr verification check staging` validates it, and the spec's section opts
in with `strategy: staging` or a per-row `- <row-id>: staging` line.

## The install contract

Any strategy that installs a build goes through the repo's own executable
`.fr/candidate-install`:

```
.fr/candidate-install <prefix> <source>
```

- `<source>` is a worktree path, or `git+<url>@<ref>` (what a pre-release
  prints). Package subdirectories of a git source are addressed with
  `#subdirectory=<path>`.
- It installs into `<prefix>` and nothing outside it. For a `uv tool` install,
  that means `UV_TOOL_DIR` and `UV_TOOL_BIN_DIR` under the prefix. The operator's
  own install is never touched, and the walk fails if it was.
- Its last line of standard output names the tool, found at `<prefix>/bin/<name>`.
- The contract mirrors all else that the repo's real installer adds (extra packages,
  plugins), so the candidate is the thing users get. For every `fr.runners` package,
  super-fr's own `.fr/candidate-install` carries the same `--with` set as `scripts/install.sh`.

A repo without it cannot use `candidate`, `client-live` or `prerelease`, and
`fr verification walk` says so by name.

## What the walk checks

`fr verification walk --run <run-id> --model <m>` always runs a baseline smoke
first: the install, the tool's `--version`, and one command in a fresh fixture
repo. Then it runs the scenario of each row that the run's spec cites, when the row's
effective strategy is the walked one. It writes a log outside the repo. The log
records the code tree, strategy, harness, model and each step's exit status. The walk
exits non-zero when any step fails.

Run it as a bare command (`fr` or `uv run
fr`, no env prefix, pipe or redirect). `deliver` only trusts a log that it can tie to
that command, to the run and strategy, and to the manifest's hash.

`walk` does not run a strategy whose `source:` is `prerelease`, because it never installs
an rc. For those rows, the PR body's `## Pre-merge verification owed` section
prints a manual route instead. Cut the rc with `fr verification prerelease`,
install it through the install contract, and run the row's scenario in the client.

## Write a scenario

A scenario is an executable script, one per row (`tests/scenarios/<row>.sh` in
this repo). It runs with the installed tool first on `PATH`, and with a fresh git
fixture as its current directory. It asserts with `grep` on the tool's output, and
exits non-zero on the first failed assertion. It never reaches a forge. See
`tests/scenarios/` for worked ones, and `tests/integration/test_scenarios.py`
for how CI installs a candidate and runs them.
