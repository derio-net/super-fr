```
.github/
  ci-budget.yaml                 ~ fr-spec-status.yml line dropped
  workflows/
    fr-spec-status.yml           - deleted (R1)
    _pr_spec_status.yml          - deleted (R1)
    ci-budget.yml                ~ "PR spec status (self)" dropped; + env UV_PYTHON (R4)
    acceptance-report.yml        ~ + env UV_PYTHON (R4)
    pages.yml                    ~ + env UV_PYTHON (R4)
    pinned-clis.yml              ~ + env UV_PYTHON (R4)
    ci.yml                       ~ + permissions: {contents: read}; job blocks kept (R5)
scripts/floors.py                ~ 3.11 prose + getattr fallback gone; regex unchanged (R2)
packages/fr/src/fr/states.py     ~ docstring: "in `fr spec status` output" (R1)
plugins/super-fr/skills/fr-progress/SKILL.md  ~ workflow sentence gone (R1)
  .opencode/…, .hermes/…         ~ regenerated mirrors
docs/explainers/fr-progress.md   ~ workflow sentence gone, reviewed stamp (R1)
docs/docs-currency.md            ~ reviewed stamp (pages.yml touched)
docs/acceptance/features/2026-11-27-ci-hygiene.yaml  + 2 rows, status ci (R4, R5)
tests/unit/
  test_ci_python_floor.py        + test_every_uv_workflow_pins_uv_python_to_the_floor (R4)
  test_ci_lanes_workflow.py      + test_ci_yml_default_token_is_read_only_contents,
                                   test_every_workflow_declares_workflow_level_permissions (R5)
  test_ci_shards.py              ~ 7-shard prose; partition splits into len(matrix shards) (R3)
  test_ci_budget.py              - test_counted_pr_spec_status_counts_every_event (R1)
.changes/feat-batch-ci-hygiene.yaml  + patch fragment
```
