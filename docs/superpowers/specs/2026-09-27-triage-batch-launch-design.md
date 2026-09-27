# Triage batch launch: session model from the orchestrator binding, and a batch declares its skill

**Status:** design · **Date:** 2026-09-27 · **Closes:** super-fr#704, super-fr#687
**Builds on:** `docs/superpowers/implemented/specs/2026-09-25-triage-batches-design.md` (§3.B launch, §3.C dispatch)

## Background

`fr triage batch dispatch` turns a group of judged issues into one run: it
resolves a launch (runner, harness, model), renders a brief, and hands both to
a run-capable runner (`fr-herdr`), which starts the harness on the model and
submits the brief as the first prompt. Two defects live in that path, both in
the brief renderer.

**#704 — one `--model` overrides every tier.** `render_brief`
(`packages/fr/src/fr/triage/batch_dispatch.py:87`) writes
`Use <model> for every subagent and every model tier.` into every brief, and
`resolve_launch` (`packages/fr/src/fr/triage/batch.py:306`) refuses a batch
that has no model on the batch or in `defaults.launch`, never consulting the
orchestrator binding (`fr models resolve --harness <h> --tier orchestrator`).
So the operator must give a model, and whatever they give is then imposed on
every phase executor and every reviewer, bypassing the `fr models` tier
bindings fr-goal otherwise uses. Wave 1 ran every subagent of every batch on
one blanket model; it cost an afternoon and four blocked sessions.

**#687 — every batch is a feature.** `render_brief` hardcodes `/fr-goal`
(`batch_dispatch.py:60`) and `batch_branch` hardcodes `feat/batch-`
(`batch.py:59`). A batch of bugs cannot dispatch `/fr-debugging`, so bug fixes
go through the feature pipeline (brainstorm, spec, plan) instead of the
debugging one (reproduce, root cause, failing test, fix).

Both issues touch the same renderer, so they ship together.

## Decisions (operator, 2026-09-27)

| id | decision |
|---|---|
| d1-no-subagent-override | No subagent-model override of any kind. The brief says nothing about subagent models; the run resolves each tier through `fr models` (repo override > user). A repo that wants different tier models sets them in its own `docs/superpowers/models.yaml`, not on a batch. |
| d2-harness-alias | The batch's `harness` is the runner's name for it (herdr: `claude`); `fr models` keys by fr's harness id (`claude-code`). fr maps the one with a fixed alias table (`claude` → `claude-code`; every other name, `opencode`/`hermes` included, as-is). When the batch, `defaults.launch` and the orchestrator binding all leave the model unset, dispatch refuses and names the exact `fr models set` that would fix it. |
| d3-theme-warning | The one-root-cause warning fires on `create` and on `edit`, whenever the resulting batch is `skill: debug` and its members carry two or more distinct non-empty themes. It warns; it never refuses. |

Decided by the brief (not operator questions): `skill: goal | debug`, default
`goal`; `--skill` on `create` and `edit`; a debug batch uses branch
`fix/batch-<id>` and a brief that starts `/fr-debugging` and states
fr-debugging's two hard stops; schema-2 `judgements.yaml` files keep loading
unchanged. `judgements.yaml` is not an artifact kind, so no stamp bump or
migration is owed.

## Design

### A. The session model (#704)

`resolve_launch(batch, config, *, orchestrator=None)` gains a keyword: a
callable `harness -> model | None` the command layer supplies. Resolution per
field is unchanged for `runner` and `harness`. For `model`:

1. `batch.launch.model`
2. `config.defaults.launch.model`
3. `orchestrator(fr_harness(harness))` — only once the harness is known

`fr_harness(name)` is the d2 alias table (`fr.triage.batch`, one dict:
`{"claude": "claude-code"}`, identity otherwise). Missing fields are refused
as today; when the model alone is missing and the harness is known, the
message adds `or bind one: fr models set --harness <fr-harness> --tier
orchestrator --model <model>`.

The returned `Launch` stays a plain `Launch`; the command layer prints where
the model came from (`model: claude-opus-5-5 (orchestrator binding)`, `(batch)`,
`(defaults.launch)`) so the dry-run shows why that model was picked.
`resolve_launch` stays pure: it never reads a file; the callable does.

**Where the binding is read.** The command layer builds the callable over
`fr.models.resolved_config(repo_cfg=…, user_cfg=…)`: the user config
(`default_models_path()`) and, when dispatch has a checkout of the target repo,
that checkout's `docs/superpowers/models.yaml` — the same repo-over-user rule
the run itself will apply, read from the repo the run will work in rather than
from the dispatcher's cwd. `REPO_MODELS_REL` moves from `commands/models_cmd.py`
to `fr/models.py` so both commands import one constant. Dispatch opens the
checkout before it resolves the launch (it already needed one; this only
reorders two lines). `dispatch --repair`'s record-missing path has no checkout
unless `--checkout` is given; it resolves against the user config then, which
only feeds the runner's liveness probe.

**The brief.** The line `Use <model> for every subagent and every model tier.`
is deleted. Nothing replaces it: fr-goal (and fr-debugging) already resolve
every subagent's tier through `fr models`, and d1 means there is nothing to
override. The session model reaches the harness through the runner payload's
`model`, where it always went. `render_brief` drops its `model` parameter.

`--model`'s help on `create`/`edit` changes from "Model for every tier." to
"Session model (the run's orchestrator); subagents use their `fr models` tiers."

### B. A batch declares its skill (#687)

`Batch.skill: Literal["goal", "debug"] = "goal"`. Because `_dump_batches`
writes with `exclude_defaults=True`, a goal batch is written exactly as today;
the key appears only on a debug batch. Every schema-2 file loads unchanged.
(An older `fr` reading a file that holds a debug batch refuses it, extra key
`skill` — the models are closed-world. That is the correct failure: it would
otherwise dispatch that batch as `/fr-goal`.)

`--skill goal|debug` on `create` and `edit` (edit only while `proposed`, like
every other field but `--order`).

**Branch.** `batch_branch(batch_id)` becomes `batch_branch(batch)`: 
`feat/batch-<id>` for goal, `fix/batch-<id>` for debug. Callers: the brief,
the member comment, the work item payload, dispatch's already-on-origin check
and record-missing's event. Everything downstream (collect's PR lookup,
stage derivation, merge) already reads `DispatchEvent.branch`, so a debug
batch's PR is found by the branch it was actually dispatched on.

**The work item.** `WorkItem.workflow` is the skill's name: `fr-goal` or
`fr-debugging`. No runner reads it today (herdr submits the brief), so this is
labelling, not behaviour; the `fr_dispatch.work_item` docstring is updated to
say so.

**The debug brief.** Same renderer, same member sections and closing refs;
differences:

- first line `/fr-debugging <title>`;
- the branch rule names `fix/batch-<id>`;
- a `## Debugging rules` block states fr-debugging's two hard stops —
  stop and ask when no confident single hypothesis forms; stop and ask after
  three failed fixes, before a fourth — and the batch's premise: the members
  were batched as ONE root cause, so if investigation finds more than one,
  stop and ask before fixing any;
- the "open a draft PR as soon as the spec is committed" rule becomes "as soon
  as the failing test is committed" (fr-debugging writes no spec).

### C. The one-root-cause warning (d3)

`fr.triage.batch.mixed_themes(batch, judgements) -> list[str]`: the sorted
distinct non-empty `theme`s of the members, returned only when the batch is
`debug` and there are two or more. `create` and `edit` print, after writing:

    warning: debug batch <id> mixes themes (a, b): a debug batch should be one root cause

A warning is stdout, exit 0.

### D. Docs

- `plugins/super-fr/skills/fr-triage/SKILL.md`: the batch schema comment
  gains `skill`; the `batch dispatch` sentence says `/fr-goal` or
  `/fr-debugging` by skill, and that the session model falls back to the
  orchestrator binding. Mirrors regenerated (`sync-opencode.py`, `sync-hermes.py`).
- A `minor` change fragment (new option, changed default behaviour).
- No explainer describes batch dispatch (`docs/explainers/` grep: none), so
  the explainers-currency rule is not triggered.

## Non-goals

- Any per-batch subagent or per-tier model override (d1).
- Changing fr-herdr's harness vocabulary (d2 bridges it instead).
- A shape manifest for fr-debugging; `WorkItem.workflow` stays a label.

## Test Plan

Unit (CI):

1. `resolve_launch` takes the model from batch, then `defaults.launch`, then
   the orchestrator callable, in that order; refuses when all three are unset,
   and the refusal names the `fr models set` line with the fr harness id.
2. `fr_harness("claude") == "claude-code"`; other names pass through.
3. A goal brief no longer contains "every subagent" or any model id; a
   golden brief pins the whole text.
4. A debug brief starts `/fr-debugging`, names `fix/batch-<id>`, states both
   hard stops and the one-root-cause rule.
5. `Batch` without `skill` loads as `goal`; a goal batch round-trips through
   `save_batches` byte-identically to today's output; a debug batch writes
   `skill: debug`.
6. `create`/`edit --skill debug` with mixed themes print the warning and
   exit 0; same themes print nothing.
7. `dispatch` (dry run) with no model anywhere but a bound orchestrator prints
   that model and `(orchestrator binding)`; the repo's
   `docs/superpowers/models.yaml` in the checkout overrides the user binding.
8. A dispatched debug batch's event records `fix/batch-<id>` and the work
   item's workflow is `fr-debugging`.

No live verification is owed beyond CI: herdr's contract (`payload.model`,
`payload.brief`) is unchanged, and it is pinned by `fr_dispatch.testing`.
