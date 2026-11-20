---
title: "Workflow shapes and the run cursor"
tldr: |
  A workflow shape is a YAML manifest listing the steps of a pipeline; the run cursor records where one run is. This page covers the commands, where a shape name is found, and how to override one.
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/workflow/**
  - packages/fr/src/fr/run/**
  - packages/fr/src/fr/commands/run_cmd.py
  - plugins/super-fr/workflows/*.yaml
reviewed: 2026-11-20 still true; the Python 3.14 floor reformats covered code (unparenthesised `except A, B:`, PEP 695 generics), syntax only (#1589); 2026-11-19 still true; run_cmd gained the declared `tests ci` brief key and the advisory-log refusal, no shape change (local-suite-cost); 2026-11-19 batch docs-wording changes help text and docstrings only (bracketed help renders, first lines shortened for STE, `fr ops gate` hint names the full scaffold command); still true; 2026-11-19 explicit merge targets preserve existing run steps and evidence; target alignment applies to review, delivery and PR creation. 2026-11-18 still true; deliver's owed closing check now counts an issue URL only on the repo's forge host (owed-followups), no shape change. 2026-11-17 still true; visual.py asks git check-ignore through fr.git.is_ignored, and fr run adopt names a plan's run after its folder (batch-acceptance-edits). 2026-11-16 still true; run_cmd.py gained the deliver check that a discharged owed issue is closed by the PR body. 2026-11-15 the deliver-evidence fixes (stale fresh log, forge read, capture wrappers) change no shape, and closeout.py changed only the DevOps brief of a finished stage (batch gate-truth)
---

# Workflow shapes and the run cursor

`/fr-goal` is not a long prompt. It is a **workflow shape**: a YAML manifest. The manifest
lists an ordered set of steps and the runner capabilities that it needs. It also names the
unit that the shape works on as a whole (`run`, `phase` or `spec`).

`/fr-goal` with no argument uses the shape named `fr-goal`. `/fr-goal fr-goal-light` picks
another shape. The shapes super-fr ships are in
[plugins/super-fr/workflows/](https://github.com/derio-net/super-fr/tree/main/plugins/super-fr/workflows).

A step is either a `cli` step or an `agent` step. `fr run advance` executes the first kind
itself. For the second kind, it prints a brief for the agent to carry out. The **run cursor**
is the file that records which step the run is on.

## The commands

```bash
fr run start <shape> --branch <b>     # resolve the shape, ensure the workspace, start the cursor
fr run target <run-id> --base <b>     # record a fetched non-default merge target before lens review
fr run advance <run-id>               # run the next cli step, or print the next agent brief
fr run resolve <run-id> --step <id> --state done   # record an agent step's outcome
fr run status <run-id>                # the cursor and every step's state
fr run adopt <plan-dir>               # give work already under way a cursor (writes it at once)
fr run adopt <plan-dir> --supersede   # replace a stranded run, keeping its history (preview unless --yes)
fr run reshape <run-id>               # move a drifted cursor onto the shape's current steps (preview unless --yes)
fr workflow check <shape>             # validate a shape; --all checks every one found
```

The cursor is a git-tracked file, `docs/superpowers/runs/<run-id>.yaml`, a sibling of the
journals. That path is the repo placement's. Under the quiet and stealth placements, the
cursor sits below the feature root. It is archived with the plan it produced.

A run without an explicit merge target keeps the remote-default behavior. Use
`fr run target` before lens review starts when the change will merge elsewhere.
It records `base_branch` without replacing the run or clearing its steps. The
same target supplies lens rules, the review diff, delivery docs/proportionality
checks and draft PR creation. A later `--base` cannot contradict that target.

`fr workflow check` validates the schema, duplicate step ids, `needs` that point nowhere,
cycles and unknown capabilities. CI runs it on every shipped shape.

## Where a shape name is found

The first hit wins:

1. `docs/superpowers/workflows/<name>.yaml` in the repo: your override, used whole.
2. `$FR_SHIPPED_WORKFLOWS_DIR/<name>.yaml`, when that variable is set. This is the escape
   hatch for tests and for harnesses that are not Claude Code.
3. The copy inside the installed `fr` package.
4. The Claude Code plugin clone under
   `~/.claude/plugins/marketplaces/derio-net--super-fr/plugins/super-fr/workflows/`.

The package copy outranks the plugin clone on purpose: it ships with the `fr` that runs the
shape. So if you upgrade `fr` and do not run the installer again, you cannot be left on a
stale shape.
It is also why `fr run start fr-goal` works on a machine with no plugin clone at all.
`fr workflow check --all` exits non-zero when no shape is found anywhere, because "nothing
installed" is a broken installation, not a clean result.

To change a shape for one repo, copy the shipped file to `docs/superpowers/workflows/` and
edit it. Run `fr workflow check <name>` before you rely on it.
