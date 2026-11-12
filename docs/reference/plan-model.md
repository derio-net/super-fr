---
title: "The plan model"
tldr: |
  A plan is a folder of small YAML files, one per phase, stored in the repo it changes. This page is the shape of that folder and the rules about who delivers what.
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/types.py
  - packages/fr/src/fr/plan/**
  - packages/fr/src/fr/commands/plan_cmd.py
reviewed: 2026-11-12 placement-resolver phase 3, plan create writes and commits on the fr branch under quiet
---

# The plan model

A plan is the written-down answer to "what will we build, in what order, and how will we
know each part is done". It lives in the same repo as the code it changes, under
`docs/superpowers/plans/`, so it is reviewed, branched and merged like code.

## One folder per plan

```
docs/superpowers/plans/<YYYY-MM-DD-slug>/
├── _meta.yaml    # slug, spec, target repo, fr_version range, schema_version
├── _prose.md     # the human-readable narrative
├── 01.yaml       # phase 1: header, tasks, steps
└── 02.yaml       # phase 2 ...
```

`_meta.yaml` names the plan, the spec it implements (`spec:`), the repo it changes
(`target_repo:`) and the range of `fr` versions allowed to read it (`fr_version:`).
Each phase file has a `phase:` header with its `number`, `title`, `tag`, `depends_on`
phases, the `acceptance` rows it moves, a model `tier` hint and the `files` it expects to
touch, followed by `tasks:`. A task holds `steps:`, and every step has an id of the form
`P<phase>.T<task>.S<step>` (for example `P2.T1.S3`) plus its text.

The `tag` is `agentic` (an agent does it) or `manual` (a human does it, such as secrets, UI
work or a deploy). Manual phases are never routed to a runner.

## Making and changing one

```bash
fr plan create --slug <slug> --target-repo <owner/repo> \
  --spec <spec-file> --phases-file <phases.yaml>   # scaffold the folder
fr plan edit <plan-dir> --tick P1.T1.S1                          # mark a step done
fr plan edit <plan-dir> --complete-phase 1                        # close a finished phase
fr plan self-review <plan-dir>                                   # soft lints beyond the schema
fr plan rework --help                                            # a sibling plan for follow-up work
fr pickup <plan-dir> --phase 2                                   # print one phase's scope for an agent
```

Run any of them with `--help` for the full flags; the skills drive these for you. Plans
are edited through the commands rather than by hand so the ticks, the spec's plan table
and the run cursor stay in agreement.

In a repository using the quiet placement, `create` writes the plan folder below this
feature's path in the `fr` worktree (`features/<feature-id>/docs/superpowers/plans/<slug>/`)
and commits it on the `fr` branch, not the feature branch (see the quiet section of
[the fr-goal explainer](../explainers/01-fr-goal.md)).

## One plan, one repo, and when PRs split

- **One plan is one repo's work.** A feature that spans repos gets one plan per repo,
  coordinated through the shared spec's "Implementation Plans" section.
- **Local runs deliver one PR.** Under `/fr-goal` every phase lands as commits on one
  branch and the whole plan arrives as a single pull request.
- **Dispatched phases deliver one PR each.** With `fr apply --to <runner>`, each phase gets
  its own tracking issue and its own PR, so each can be reviewed alone. See
  [dispatch lifecycle](dispatch-lifecycle.md).

The skills that write and run plans are described in
[From an idea to a plan](../explainers/fr-brainstorming-and-plan.md).
