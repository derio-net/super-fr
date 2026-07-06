# Design: README UX pass + plan-config dead-key cleanup

- **Status:** Reviewed (against Q&A answers + codebase reality, 2026-06-16)
- **Date:** 2026-06-16
- **Slug:** readme-ux-and-plan-config-cleanup
- **Author:** fr-goal (operator: derio)

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|-------------|------|--------|
| 2026-06-16-readme-ux-and-plan-config-cleanup | `derio-net/super-fr` | `2026-06-16-readme-ux-and-plan-config-cleanup` | — |

## Problem

Two usability/cleanup goals for super-fr:

1. **Dead config in `plan-config.yaml`.** Investigation (last session, re-confirmed)
   shows the per-repo `docs/superpowers/plan-config.yaml` carries keys nothing
   reads:
   - **Live** (read by `scripts/validate-plans.sh`): `plan.filename`,
     `header.required`, `header.status_values`.
   - **Dead** (read by no code): `plan.save_to`, and the **entire `dispatch:`
     block** (`target`, `owner`, `project_board`, `default_repo`, `labels`).
     The only code tie is the docstring of `labels.py::def_for_name`, and that
     function has **zero callers** (verified across `packages/` + `tests/`) — so
     even the label-override mechanism it documents is dead.

   The dead keys mislead readers into thinking they configure dispatch. They
   should be removed from this repo's file, stopped from being generated, and
   actively stripped from any repo that `fr repair` / `fr migrate` touches.

2. **Maintainer-oriented README.** The README front-loads two architecture
   diagrams *before* the Quickstart, lists Python-package internals in the first
   table, mixes everyday and maintenance CLI commands, and the skill tables
   (`Skill | Description`) give no "when do I reach for this" guidance. A new
   user can't get to first-success quickly.

## Goals

- Remove the dead `plan-config.yaml` keys from this repo's file; stop the
  `fr repos sync` template from emitting a dispatch stub; delete the dead
  `def_for_name` helper.
- Make `fr repair` and `fr migrate v1-to-v2` **strip the dead keys** from any
  `plan-config.yaml` they encounter, idempotently.
- Restructure the README to a **user-first** information architecture (single
  file, progressive disclosure), with the skill tables gaining `How invoked`
  and `When` columns.

## Non-goals

- Changing what `validate-plans.sh` reads (the live profile is unchanged).
- Re-introducing file-driven dispatch config (the dead keys are gone, not
  relocated).
- Splitting the README into multiple docs (operator chose one file).
- Touching skill frontmatter/`SKILL.md` files (README-only doc change).

## Design

### Part A — plan-config dead-key normalizer (`fr.plan_config`)

A new pure module `packages/fr/src/fr/plan_config.py` with a text-based
stripper (no YAML round-trip — preserve live keys' formatting and comments
byte-for-byte):

```
strip_dead_keys(text: str) -> tuple[str, list[str]]
```

Returns the rewritten text and a list of human-readable removals
(`["plan.save_to", "dispatch"]`). Contract:

- Remove the `save_to:` line **inside the top-level `plan:` mapping** (a line
  matching `^\s+save_to:` within the `plan:` block).
- Remove the **entire top-level `dispatch:` block**: the line matching
  `^dispatch:` plus every following more-indented or blank line, stopping at the
  next top-level key (`^\S`) or EOF.
- Only touch **active** keys — a commented `# dispatch:` / `# save_to:` is left
  alone (it's already inert).
- Collapse at most one blank line left behind by a removed block.
- **Idempotent:** no dead keys → returns the input unchanged and `[]`.

A sibling `strip_dead_keys_file(path) -> list[str]` reads/writes the canonical
`docs/superpowers/plan-config.yaml` at a repo root and returns the removals
(empty list if the file is absent or already clean).

This lives in the base `fr` package; it imports only stdlib (`re`), so no
layering concern.

### Part B — wire into `fr repair` and `fr migrate v1-to-v2`

- **`fr repair`** (`repair.py` / `repair_cmd.py`): repair's remit is "normalize
  stale config idempotently." Extend its pass to call `strip_dead_keys_file` on
  the repo's `plan-config.yaml`. Surface each removal through the existing
  `RepairResult` reporting as a new rewrite kind, e.g.
  `plan-config.yaml · removed dead key: dispatch`. Honors the existing dry-run
  default / `--yes` (no write on dry-run; the report lists what *would* be
  removed).
- **`fr migrate v1-to-v2`** (`migrate.py`): it already rewrites specs as part of
  the wholesale v1→v2 conversion. Add a `strip_dead_keys_file` call on the
  repo's `plan-config.yaml` to the same pass, reported in the migrate summary.
  Honors migrate's dry-run/`--yes` convention.

Both share the one `fr.plan_config` implementation — no duplicated logic.

### Part C — stop generating the stub + remove dead helper

- **`render_plan_config`** (`repos.py`): drop the commented `# dispatch:` stub
  block entirely. The generated `plan-config.yaml` becomes just the live
  validator profile (`plan.filename`, `header.*`). Update the
  `test_render_plan_config_dispatch_is_commented_and_substituted` test → assert
  the template contains **no** `dispatch` line (commented or otherwise) and no
  `owner` arg is needed; simplify the signature if `owner`/`repo` become unused
  (keep `repo` only if still referenced, else drop both args — see note).
- **This repo's `docs/superpowers/plan-config.yaml`:** strip `plan.save_to` +
  the `dispatch:` block (leaving the live profile). This is the dogfood proof
  the normalizer's output is what we want.
- **`def_for_name`** (`labels.py:193`): delete the function and its docstring
  (zero callers, not exported, no tests).

> Note on `render_plan_config` signature: today it takes `(owner, repo)` only to
> fill the dispatch stub. With the stub gone, both args are unused. The plan
> will drop them and update the one call site in `repos_cmd.py` and the tests.

### Part D — README user-first restructure (single file)

Re-sequence to this information architecture (progressive disclosure — everyday
surface first, internals demoted), rewriting prose to be benefit-led and
user-oriented (lean on `crafting-effective-readmes` +
`writing-clearly-and-concisely`):

1. **Intro** — benefit-led lede (what you get: a feature description → a
   reviewed PR), badges, one-line "two Claude Code plugins" framing. The
   Python-package breakdown moves OUT of here.
2. **Quickstart** — Install (plugin / one-liner / CLI-only) → **Run your first
   goal** (`/fr-goal …`). Moved above the diagrams so first-success comes early.
3. **Skills** — the two tables, reformatted to **4 columns**
   (`Skill | What it does | How invoked | When`), content per the tables below.
4. **How it works** — the two existing Mermaid flow diagrams + the
   "flows compose" note, relocated here (kept, not cut).
5. **Isolation** — worktrees + devcontainers (kept; users need the model).
6. **Reference** — the full `fr` CLI table **grouped into Everyday vs
   Maintenance**, the Plan model, the Label lifecycle, the Per-repo profile
   (`plan-config.yaml` + `fr repos sync`; reworded since the dispatch keys no
   longer exist), and a short **Components** subsection listing the
   `fr` / `fr-dispatch` / `fr-vk` packages (relocated from the top).
7. **Requirements / maintainers** — requirements list; a one-liner pointing
   maintainers at `CLAUDE.md` for the release/version rules.

#### super-fr skill table (final content)

| Skill | What it does | How invoked | When |
|-------|--------------|-------------|------|
| `fr-goal` | Brainstorm → spec → plan → TDD → reviewed PR, unattended | `/fr-goal <description>` | You want a feature built end-to-end without babysitting — the usual entry point |
| `fr-brainstorming` | superpowers brainstorming, inside isolation from the first command | `/fr-brainstorming` or auto (fr-goal step 1) | Designing a feature into a spec before building |
| `fr-debugging` | systematic-debugging in isolation → fix-PR | `/fr-debugging` or auto | A bug, failing test, or unexpected behavior to root-cause + fix |
| `fr-plan` | Phase-structured plan-as-folder + spec index | `/fr-plan` or auto (after a spec) | Turning an approved design into an executable plan |
| `fr-execute` | Implement one agentic phase (Phase > Task > Step), TDD | agent-facing; auto in fr-goal / dispatch | Carrying out assigned phase work (rarely called directly) |
| `fr-isolation` | Worktree + devcontainer lifecycle | `/fr-isolation` or auto | Running anything that must not touch your base checkout; post-merge cleanup |
| `fr-init` | Scan repo, interview, scaffold devcontainer profiles | `/fr-init` or auto (first isolated run) | First fr use in a repo with no devcontainer profile |
| `fr-progress` | Status board, drift audit, spec rollup | `/fr-progress` | "What's in progress?", auditing plan/spec drift |

#### super-fr-dispatch skill table (final content)

| Skill | What it does | How invoked | When |
|-------|--------------|-------------|------|
| `fr-dispatch` | Queue a merged plan's phases to a runner + reconcile Issues | `/fr-dispatch` (`fr apply --to <runner>`) | You merged a plan and want its phases run asynchronously |
| `fr-runner` | Operate/debug a runner: tick health, stuck phases, metrics | `/fr-runner` | A dispatched phase is stuck, or checking runner/bridge health |

## Affected files

- `packages/fr/src/fr/plan_config.py` (new — normalizer)
- `packages/fr/src/fr/repair.py`, `packages/fr/src/fr/commands/repair_cmd.py` (wire + report)
- `packages/fr/src/fr/migrate.py` (wire + report)
- `packages/fr/src/fr/repos.py` (drop dispatch stub from `render_plan_config`)
- `packages/fr/src/fr/commands/repos_cmd.py` (update call site if signature changes)
- `packages/fr/src/fr/labels.py` (delete `def_for_name`)
- `docs/superpowers/plan-config.yaml` (strip dead keys — dogfood)
- `README.md` (restructure)
- `tests/` (new `test_plan_config.py`; update repair/migrate/repos tests)
- version-bump set (pyproject ×N, plugin.json ×2, marketplace.json, uv.lock)

## Testing strategy

- **`fr.plan_config` (TDD):** strips `save_to`; strips a `dispatch:` block at
  middle and at EOF; preserves live keys + comments + a commented dispatch stub;
  idempotent on an already-clean file; absent file → `[]`; blank-line collapse.
- **`fr repair` (TDD):** a repo whose `plan-config.yaml` has dead keys →
  dry-run reports the removals and writes nothing; `--yes` writes the stripped
  file; a clean repo → no plan-config rewrite reported; repair stays idempotent.
- **`fr migrate v1-to-v2` (TDD):** migration of a repo with a dead-key
  `plan-config.yaml` also strips it; reported in the summary.
- **`render_plan_config` (update):** generated file has no `dispatch` line and
  parses as the live profile.
- **README:** no automated assertion beyond existing doc/link validation; the
  restructure is verified by review + render. Confirm `test_skill_validation`
  and any link checks still pass.
- Full local gate green before delivery (ruff format/check, mypy, pytest,
  `bump-version.py --check`).

## Version

Touches `packages/*/src` and adds user-visible behavior to `fr repair` /
`fr migrate` → **version bump required**. Treat as **minor** (new mandatory
normalization behavior on existing commands); reconcile from main's value at
merge time. Patch is acceptable if reviewers consider it a pure enhancement.

## Open questions

None blocking. The normalizer is text-based to preserve formatting/comments,
matching `repair.py`'s existing byte-preserving philosophy rather than a
PyYAML round-trip.
