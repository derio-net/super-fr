# Split plan_ops.py: self-review, the spec table, the refactor-gate read and rework

Issue: derio-net/super-fr#1518 (architecture review for #1318, section 5.4 of
`docs/superpowers/audits/2026-11-16-architecture-review.md`).

## Background

`packages/fr/src/fr/plan_ops.py` is 2,575 lines against a budget of 2,600
(`tests/unit/test_tripwire_module_budget.py:28`). It holds the plan writers and also
three groups of code that are not writers:

- the plan self-review, `self_review` (`plan_ops.py:1365`), its lint vocabulary
  (`_PHASE_REF_NOTE_RE` `:1087` to `_trailing_manual_block` `:1338`) and its sub-checks
  (`_manual_placement_issues` `:1569` to `_scope_field_issues` `:2505`), about 1,460 lines,
  all pure decisions over a parsed `Plan` plus journal reads;
- the spec "Implementation Plans" table (`_SPEC_TABLE_HEADER_RE` `:540` to
  `_append_spec_row` `:615`), text edits plus one write, called by `create` and
  `rework_create` and by `fr/migrate.py:757-770`;
- `_refactor_justifications` (`:2549`) with `_TASK_ID_RE` (`:1088`), whose only caller is
  `fr/record/gates.py:29`.

Rework (`_REWORK_SUFFIX_RE` `:808` to `rework_list` `:1019`) is a fourth group with its own
decisions. It uses the plumbing `_stage` (`:79`, through `worktree_of` `:70`), `_yaml_dump`
(`:115`, through `_coerce_step_texts` `:99`), `PlanEditError` (`:62`) and the spec table,
and `tests/unit/test_plan_ops_feature_root.py:20` patches `plan_ops.space_for` to steer
`_feature_root_of`.

The spec table raises `PlanEditError` while `create` and rework call the table, so moving
the table alone makes `plan_ops` and the table import each other. Moving rework alone makes
`plan_ops` (re-exporting rework) and rework (using the plumbing) import each other.

Two journal reads share one shape: `_spec_journal_entries` (`:2159`, spec scope) and the
read inside `_refactor_justifications` (`:2553-2566`, plan scope). Both resolve the read
path (active else archived), treat a missing file as no entries, and treat a
`JournalParseError` as no entries.

`packages/fr/src/fr/plan/` is the legacy v1 plan reader; its `__init__.py` says the whole
directory is to be deleted once v1 migration is no longer needed. New code does not go
there.

Every write in `plan_ops.py` already goes through `write_text_atomic`, and
`tests/unit/test_run_durability.py:105` (`test_no_plain_write_text_in_the_cursor_and_plan_writers`)
forbids a plain `write_text` there. The one raw write this change touches is
`fr/migrate.py:761` (`spec_path.write_text(text)`); it stays raw (#1524 owns that class).
Excluded on purpose (issue #1518): `tick`/`complete_phase` stay in `plan_ops.py`
(retiring them is design 6.4, #1522).

## Requirements

R1. `_refactor_justifications` and `_TASK_ID_RE` move to `fr/record/gates.py`, their one caller.
R2. The lint vocabulary, `self_review` and its sub-checks move to a new package `fr/plan_review/`, split into more than one module.
R3. One helper reads a journal's entries for a scope and slug (read-resolved, missing or unparseable file is no entries); the spec-journal read of self-review and the plan-journal read of `_refactor_justifications` both use it.
R4. `PlanEditError` moves to a new leaf module `fr/plan_errors.py` that imports nothing from `fr.plan_ops`.
R5. The spec "Implementation Plans" table code moves to a new module `fr/spec_table.py`.
R6. `worktree_of`, `_stage`, `_coerce_step_texts` and `_yaml_dump` move to a new private module `fr/_plan_io.py`.
R7. Rework (`_REWORK_SUFFIX_RE` through `rework_list`, with `ReworkRecord`) moves to a new module `fr/plan_rework.py`.
R8. No import cycle: `plan_errors`, `_plan_io`, `spec_table`, `plan_review` and `plan_rework` never import `fr.plan_ops`.
R9. Every public name `fr.plan_ops` has today stays importable from it — `StepSpec`, `TaskSpec`, `PhaseSpec`, `PlanEditError`, `worktree_of`, `rewrite_phase_text`, `create`, `tick`, `complete_phase`, `set_tracking_issue`, `clear_tracking_issue`, `rework_create`, `rework_add_origin`, `rework_list`, `ReworkRecord`, `self_review`, `ReviewIssue`, `OPS_FR_FLOOR` — and so do `_trailing_manual_block` and `_manual_placement_issues`.
R10. Every caller under `packages/` imports a moved name from its new home, not through `fr.plan_ops`, and a docstring under `packages/` that names a moved name's old path names its new one.
R11. Tests that import or patch a moved private name import or patch it in its new home; no test assertion changes. The plain-`write_text` guard's parameter list widens to every new module holding a writer (`_plan_io.py`, `spec_table.py`, `plan_rework.py`), so the guard covers the same writes as before.
R12. Behaviour is unchanged: self-review returns the same issues in the same order, and every writer writes and stages the same files.
R13. The `plan_ops.py` budget in `test_tripwire_module_budget.py` drops to within its 400-line headroom of the new size; `plan_ops.py` stays a held module.
R14. `docs/explainers/01-fr-goal.md` names `self_review`'s new path; every page `fr docs check` reports for a file this change edits (no page covers `plan_ops.py` itself) gets its `reviewed` stamp moved with the note `still true, import-only change` (a comma: a colon followed by a space breaks the page's YAML front matter), or an edit where a claim moved.
R15. The PR adds the change fragment `.changes/feat-batch-arch-plan-ops-split.yaml` with `bump: patch`.

## Design

Every move is a cut and paste: no function body changes except the journal read (R3) and
the import lines. A moved function keeps its name and its docstring.

**`fr/plan_errors.py`** holds `PlanEditError` alone. Every other new module that raises it
imports it from here.

**`fr/_plan_io.py`** holds `worktree_of`, `_stage`, `_coerce_step_texts` and `_yaml_dump`.
`plan_ops` imports them from here for its own writers; `worktree_of` is re-exported.
`fr/migrate.py` and `fr/commands/plan_cmd.py` import `_stage` and `worktree_of` from here.

**`fr/spec_table.py`** holds the table section: `_SPEC_TABLE_HEADER_RE`,
`_CANONICAL_HEADER_LINE`, `_CANONICAL_HEADER_CELLS`, `_CANONICAL_HEADER_SEPARATOR`,
`_header_hint`, `_first_table_line`, `_check_table_header`, `_ensure_section_text`,
`_validate_spec_section` and `_append_spec_row`. It imports `PlanEditError` from
`fr.plan_errors`. `create` (in `plan_ops`) and `rework_create` (in `plan_rework`) and
`fr/migrate.py` import from here.

**`fr/plan_rework.py`** holds `_REWORK_SUFFIX_RE`, `_PLAN_HOMES`, `_feature_root_of`,
`_next_rework_number` (its nested `_scan` moves with it), `rework_create`, `_find_prior_rework`, `rework_add_origin`, `ReworkRecord` and `rework_list`. It imports
`space_for` and the path helpers from `fr.artifacts.paths` itself, so the test that steered
`_feature_root_of` patches `fr.plan_rework.space_for`.

**`fr/plan_review/`** is a package:

- `vocabulary.py` — the lint vocabulary: regexes, phrase tables, `_strip_fenced_code`,
  `_note_defers_forward`, `_not_ticked_steps`;
- `journal.py` — `_spec_journal_slug` and the one journal reader of R3,
  `journal_entries(repo_root, scope, slug)`, returning `[]` for a missing or unparseable
  file; `_spec_journal_entries(plan)` becomes a call to it;
- `checks.py` — `ReviewIssue`, `_trailing_manual_block` and every sub-check, the ops floor
  (`OPS_FR_FLOOR`) among them;
- `__init__.py` — `self_review` and the re-exports `ReviewIssue`, `OPS_FR_FLOOR`,
  `_trailing_manual_block` and `_manual_placement_issues`.

The executor may split `checks.py` further along the sub-checks' lines if one module grows
past about 800 lines; the package's `__init__` keeps the same names either way.

**`fr/record/gates.py`** gains `_TASK_ID_RE` and `_refactor_justifications`, the latter
reading the plan journal through `fr.plan_review.journal.journal_entries`. It keeps its own
name `_TASK_ID_RE`; `fr/record/model.py:112` has an unrelated anchored pattern of the same
name, and the two are not merged.

**`fr/plan_ops.py`** keeps the writers (`create` and its helpers, `tick`, `complete_phase`,
the tracking-issue writers, `rewrite_phase_text`, `PhaseSpec`, `_now_iso`) and re-exports
`PlanEditError`, `worktree_of`, `rework_create`, `rework_add_origin`, `rework_list`,
`ReworkRecord`, `self_review`, `ReviewIssue`, `OPS_FR_FLOOR`, `_trailing_manual_block` and
`_manual_placement_issues`. Its module docstring says where the rest went.

**Callers** (R10): `fr/migrate.py` (`_stage`, the table names, `PlanEditError`),
`fr/commands/plan_cmd.py` (its `plan_ops` import list and `worktree_of`),
`fr/record/gates.py`, `fr/commands/run_cmd.py:5131` (`_manual_placement_issues`, from
`fr.plan_review`), `fr/record/apply.py` (unchanged: `rewrite_phase_text` and `_now_iso`
stay), `fr/commands/apply_cmd.py:47` and `fr/commands/undispatch_cmd.py:32` (`PlanEditError`
from `fr.plan_errors`; their `plan_ops` module import stays, because tests patch
`apply_cmd.plan_ops.set_tracking_issue`), `fr_dispatch/__init__.py` (`PlanEditError` from
`fr.plan_errors`; its `plan_ops.set_tracking_issue` call stays, because tests patch it
there). `plan_cmd.py` imports the rework names from `fr.plan_rework` and `self_review` from
`fr.plan_review`. The docstrings at `run_cmd.py:798`, `run_cmd.py:5123` and `cli.py:7` name the
new paths.

**Order of the moves** keeps every intermediate commit importable: `plan_errors` and
`_plan_io` first, then `spec_table`, then `plan_review` with the journal helper and the
`gates.py` move, then `plan_rework`.

## Design shape

```
packages/fr/src/fr/
  plan_ops.py            ~ keeps create, tick, complete_phase, tracking-issue writers,
                           rewrite_phase_text, PhaseSpec; re-exports the public names  R9 R13
  plan_errors.py         + PlanEditError (leaf)                                         R4
  _plan_io.py            + worktree_of, _stage, _coerce_step_texts, _yaml_dump          R6
  spec_table.py          + "Implementation Plans" table (raises PlanEditError)          R5
  plan_rework.py         + rework_create, rework_add_origin, rework_list, ReworkRecord  R7
  plan_review/           + self-review package                                          R2
    __init__.py            self_review, re-exports
    vocabulary.py          lint regexes and text helpers
    journal.py             journal_entries(root, scope, slug) — the one reader          R3
    checks.py              ReviewIssue, _trailing_manual_block, every sub-check
  record/gates.py        ~ + _TASK_ID_RE, _refactor_justifications (via journal_entries) R1
  migrate.py, cli.py, commands/{plan,run,apply,undispatch}_cmd.py,
  ../../fr-dispatch/src/fr_dispatch/__init__.py
                         ~ import moved names from their new homes; docstrings         R10
tests/unit/test_tripwire_module_budget.py   ~ plan_ops.py budget lowered               R13
tests/unit/*                ~ private imports and the space_for patch repointed         R11
tests/unit/test_run_durability.py           ~ write_text guard covers the new writers   R11
docs/explainers/01-fr-goal.md               ~ self_review's path                        R14
docs/** pages covering an edited caller     ~ reviewed stamp: import-only change        R14
.changes/feat-batch-arch-plan-ops-split.yaml  + bump: patch                             R15
```

```
import direction (no cycle, R8):

_plan_io     imports none of the new modules
plan_errors  <-  spec_table  <-  plan_rework  <-  plan_ops (re-export), plan_cmd
plan_errors  <-  plan_ops, migrate, apply_cmd, undispatch_cmd, fr_dispatch
spec_table   <-  plan_ops, migrate
_plan_io     <-  plan_rework, plan_ops, migrate, plan_cmd
plan_review  <-  plan_ops (re-export), plan_cmd, record/gates, run_cmd
```

## Verification

strategy: none
gate: developer
settle.conflicts: report — batch arch-plan-ops-split: the wave driver owns this PR's mergeability
settle.ci: report — batch arch-plan-ops-split: the wave driver owns this PR's CI

The change has no behaviour of its own: the existing suite, unchanged except for import
lines and the one repointed patch, is the evidence, run by this PR's CI. No acceptance rows
are added.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-27-plan-ops-split | `derio-net/super-fr` | `2026-11-27-plan-ops-split` | — |
