# Journal: 2026-09-27-archive-repair-scope-regressions

<!-- fr:journal kind=repro scope=debug id=186d5c4d3194 created=2026-09-27T05:09:06 -->
### 186d5c4d3194 · repro · fr plan create re-run after writing the spec raises 'plan folder already exists'

create(spec='docs/superpowers/specs/<x>.md') with no spec file, write the spec, re-run the identical create → PlanEditError (bbfc2627). Pre-#697 (563c2108) the re-run appended the missing row. Pinned by tests/unit/test_v2_plan_ops.py::test_create_rerun_after_spec_is_written_appends_row_and_canonicalizes (red).
