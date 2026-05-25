---
name: vk-plan
description: >
  Write phase-structured plans with operator collaboration. Use when:
  "write a plan", "vk plan", "create a plan". Invoked by brainstorming handoff.
---

# vk-plan

Produce implementation plans through collaborative dialogue. Conversational
parts stay here; mechanical parts delegate to the `vk plan` CLI.

**Announce at start:** "I'm using vk-plan to create the implementation plan."

## Format (v2 plan-as-folder)

A plan is a directory under `docs/superpowers/plans/<slug>/` containing:

- `_meta.yaml` — schema_version, plan slug, spec ref, target_repo, vk_version,
  created date, optional rework metadata (`parent_plan`, `prior_rework`,
  `origin_items`).
  - **`spec` ref notation:** a same-repo spec is a plain repo-relative path
    (`docs/superpowers/specs/<file>.md`). A spec that lives in **another repo**
    MUST use the cross-repo form `<owner>/<repo>:<path-in-that-repo>` (e.g.
    `derio-net/frank:docs/superpowers/specs/<file>.md`). Without the
    `owner/repo:` prefix, `vk apply`'s reachability gate treats it as a missing
    same-repo file and refuses to dispatch. `vk plan self-review` warns when a
    same-repo-form spec doesn't resolve locally (#248).
- `_prose.md` — the human-readable narrative. Tooling never parses this; it's
  for humans (and the implementing agent).
- `NN.yaml` (one file per phase, two-digit zero-padded: `01.yaml`, `02.yaml`,
  …, `99.yaml`) — phase header, tasks, steps, and per-step state. Per-phase
  files prevent merge conflicts when parallel branches tick different phases.

Every step id follows `P<n>.T<n>.S<n>` (phase number, task number, step
number). The renderer / observer / diff / apply chain depends on this shape.

## Procedure

1. Read context (recent commits, existing plans, spec file).
2. Confirm scope. Decompose if too large.
3. Propose 2-3 approaches with tradeoffs. Recommend one.
4. Present plan structure section by section, get approval.
5. Scaffold the plan folder:
   ```bash
   vk plan create --slug <YYYY-MM-DD-slug> --target-repo <owner/repo> \
       --spec docs/superpowers/specs/<spec-file>.md \
       --phases-file <phases.yaml> \
       --prose-file <prose.md>
   ```
   `vk plan create` ALSO appends a row to the spec's `## Implementation Plans`
   table — there is no separate spec-index step.
6. Iterate on the prose / per-phase yaml via the Edit tool.
7. Run self-review: `vk plan self-review <plan-dir>`.
8. Hand off for execution:
   - `vk apply <plan-dir>` — render → observe → diff → preview (default
     dry-run). Add `--yes` to actually create / update GitHub Issues.
   - The implementing agent uses `vk pickup <plan-dir> --phase N` to receive
     the phase scope as markdown.

## Rules

- TDD: test first, always. No speculative generality.
- No placeholders: every step has actual code, commands, expected output.
- Bite-sized steps: 2-5 minutes each.
- Use BEGIN/END markers for full-file embeds, not nested fences.
- **Cross-repo completeness:** If the spec lists multiple plans across repos,
  write ALL of them before offering the execution handoff. For each target
  repo: scaffold the plan in that repo's `docs/superpowers/plans/` directory.
  `vk plan create` updates the spec table automatically.

## Dependency declarations

Each per-phase yaml declares its blockers via `phase.depends_on: [N, ...]`
(integers, comma-separated when multiple).

- Root phases: `depends_on: []`.
- Non-root phases: `depends_on: [1, 2]` for fan-in.
- Deps are backward-only: phase N may only reference phases < N.
- Cycles are caught by `vk plan self-review`.

## Rework plans

After a parent plan ships, defer surfaced-but-unrealised items into a separate
rework plan — do not reopen the parent.

- `vk plan rework <parent-plan-dir>` scaffolds a sibling
  `<parent-slug>-rework-N/` folder, adds `parent_plan` (and `prior_rework` if
  N>1) to its `_meta.yaml`, and appends a row to the spec table.
- `vk plan rework-add <rework-dir> --item ... --source ... --track ...`
  appends an entry to `_meta.origin_items`. `--track` is free-form (canonical
  tokens `development`, `operations`, `decision`; compounds like
  `decision → development` accepted).
- `vk plan rework-list [--include-archived]` surfaces open reworks.

## Integration

- Upstream: brainstorming hands off via vk-plan-override.
- Downstream: `vk apply` for GitHub-side work; `executing-plans` for the
  agent loop.
