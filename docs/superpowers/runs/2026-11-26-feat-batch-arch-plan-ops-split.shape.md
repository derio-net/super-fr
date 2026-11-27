```
packages/fr/src/fr/
  plan_ops.py      ~ 2575 -> 641 lines: create, tick, complete_phase, tracking issue,
                     rewrite_phase_text; re-exports every moved public name           R9 R13
+ plan_errors.py      10  PlanEditError (leaf: imports nothing of fr's plan code)      R4
+ _plan_io.py         57  worktree_of, _stage, _coerce_step_texts, _yaml_dump          R6
+ spec_table.py      141  the spec's Implementation Plans table                        R5
+ plan_rework.py     293  rework_create, rework_add_origin, rework_list, ReworkRecord  R7
+ plan_review/                                                                         R2
    __init__.py      248  self_review (+ ReviewIssue, OPS_FR_FLOOR re-exported)
    vocabulary.py    251  lint regexes, phrase tables, _strip_fenced_code
    journal.py        54  journal_entries(repo_root, scope, slug) — the one reader     R3
    checks.py        624  ReviewIssue, every sub-check but sizing
    sizing.py        388  phase-sizing and tier checks
  record/gates.py  ~ + _refactor_justifications, _TASK_ID_RE (via journal_entries)     R1

imports (arrow = "imports from"; no new module imports plan_ops)                       R8
  plan_ops ──▶ plan_errors, _plan_io, spec_table, plan_rework, plan_review
  plan_rework ──▶ plan_errors, _plan_io, spec_table, artifacts.paths
  plan_review ──▶ plan_errors, journal       record/gates ──▶ plan_review.journal (lazy)

callers ~ import from the new homes                                                    R10
  migrate.py, cli.py, commands/{plan,run,apply,undispatch}_cmd.py, fr_dispatch/__init__.py
tests/unit/test_plan_ops_split.py   + import direction, re-exports are the same objects R8 R9
tests/unit/ (7 files)   ~ imports and patch targets only; no assertion changed           R11
tests/unit/test_run_durability.py   ~ write_text guard + _plan_io, spec_table, plan_rework R11
tests/unit/test_tripwire_module_budget.py   ~ plan_ops.py budget -> 700                  R13
docs/explainers/01-fr-goal.md ~ self_review's new path; 6 pages: reviewed stamps        R14
.changes/feat-batch-arch-plan-ops-split.yaml  + bump: patch                            R15
```
