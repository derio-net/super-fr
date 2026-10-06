# Verification strategies

A verification strategy says how a change is proven before (or after) it merges.
A run's spec names one in its `## Verification` section; `fr verification walk`
runs the pre-merge ones; `deliver` refuses to finish a run whose walk is owed
and missing. This page is for the person who writes a strategy, or makes a repo
usable by one.

## The four that ship

| Strategy | When | Driver | Source | What it does |
|---|---|---|---|---|
| `candidate` | pre-merge | agent | the PR's worktree | installs the PR's build into a throwaway prefix, runs each row's scenario in a fresh fixture repo |
| `client-live` | pre-merge | operator | the PR's worktree | the same install; the operator drives the scenario inside a real client repo (`--client <path>`) |
| `prerelease` | pre-merge | operator | an on-demand rc tag | installs from `fr verification prerelease --branch <b>`'s output; `fr verification walk` refuses it (it never runs a `source: prerelease` strategy), and the PR body prints a manual route for each row instead |
| `live` | post-merge | operator | none | the released build, run by the operator after merge |

`fr verification list` shows every strategy that resolves and where each came
from; `fr verification check <name>` (or `--all`) validates manifests.

## Resolution order

A strategy name resolves, first hit wins, a repo file replacing a shipped one
wholesale (no merging of fields):

1. `docs/superpowers/verifications/<name>.yaml` in the repo;
2. `$FR_SHIPPED_VERIFICATIONS_DIR/<name>.yaml`, an explicit escape;
3. the manifests inside the `fr` wheel;
4. the plugin clone's `plugins/super-fr/verifications/<name>.yaml`.

A manifest whose `verification:` does not match its file name is refused. The
word `none` is reserved: it is not a strategy, it marks a row verified some
other way.

## Authoring a strategy

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
notes: free text
```

`install` and `scenario` are a string (split like a shell would) or a list of
strings. They may interpolate these placeholders and no others:

| Placeholder | Value |
|---|---|
| `{repo}`, `{worktree}`, `{source}` | the checkout being verified (for `prerelease`, the rc source) |
| `{prefix}` | a fresh temporary directory outside the repo; everything the install creates goes here |
| `{bin}` | `<prefix>/bin`, put first on `PATH` for every step |
| `{fixture}` | a fresh `git init` repo; each row's scenario runs in a copy of it |
| `{client}` | the `--client` repo, else the fixture |
| `{scenario}` | the row's `scenario:` script, repo-relative in the matrix |

`fr verification check` refuses a post-merge strategy that installs anything (the
released build is what runs), an agent-driven pre-merge strategy with no
`scenario` template, and a `{source}` placeholder when `source:` is `none`. A row
on an agent-driven pre-merge strategy also needs a `scenario:` on its matrix row;
`fr plan self-review` and `deliver` refuse one without.

### Example: a `staging` strategy

Verify the PR's build against a staging backend, driven by an operator. The
install comes from the PR's worktree build (`{worktree}`; `source: worktree`,
unless the manifest says otherwise). The walk still requires a `scenario:` on
every row it covers and runs that scenario after the install and smoke, so the
scenario is what reaches staging; the operator supplies the staging-wired
client with `--client`:

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
- It installs into `<prefix>` and nothing outside it. For a `uv tool` install
  that means `UV_TOOL_DIR` and `UV_TOOL_BIN_DIR` under the prefix: the operator's
  own install is never touched, and the walk fails if it was.
- Its last line of standard output names the tool, found at `<prefix>/bin/<name>`.
- Whatever else the repo's real installer adds (extra packages, plugins) the
  contract mirrors, so the candidate is the thing users get. super-fr's own
  `.fr/candidate-install` carries the same `--with` set as `scripts/install.sh`
  for every `fr.runners` package.

A repo without it cannot use `candidate`, `client-live` or `prerelease`, and
`fr verification walk` says so by name.

## What the walk checks

`fr verification walk --run <run-id> --model <m>` always runs a baseline smoke
first: the install, the tool's `--version`, and one command in a fresh fixture
repo. It then runs the scenario of each row the run's spec cites whose
effective strategy is the walked one. It writes a log outside the repo that
records the code tree, strategy, harness, model and each step's exit status, and
exits non-zero when any step fails. Run it as a bare command (`fr` or `uv run
fr`, no env prefix, pipe or redirect): `deliver` only trusts a log it can tie to
that command, to the run and strategy, and to the manifest's hash.

`walk` refuses a strategy whose `source:` is `prerelease`: it never installs
an rc. For those rows the PR body's `## Pre-merge verification owed` section
prints a manual route instead (cut the rc with `fr verification prerelease`,
install it through the install contract, run the row's scenario in the client).

## Writing a scenario

A scenario is an executable script, one per row (`tests/scenarios/<row>.sh` in
this repo). It runs with the installed tool first on `PATH` and a fresh git
fixture as its working directory, asserts with `grep` on the tool's output, and
exits non-zero on the first failed assertion. It never reaches a forge. See
`tests/scenarios/` for six worked ones, and `tests/integration/test_scenarios.py`
for how CI installs a candidate and runs them.
