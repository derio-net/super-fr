# Journal: 2026-09-27-archive-repair-scope-regressions

<!-- fr:journal kind=repro scope=debug id=186d5c4d3194 created=2026-09-27T05:09:06 -->
### 186d5c4d3194 · repro · fr plan create re-run after writing the spec raises 'plan folder already exists'

create(spec='docs/superpowers/specs/<x>.md') with no spec file, write the spec, re-run the identical create → PlanEditError (bbfc2627). Pre-#697 (563c2108) the re-run appended the missing row. Pinned by tests/unit/test_v2_plan_ops.py::test_create_rerun_after_spec_is_written_appends_row_and_canonicalizes (red).

<!-- fr:journal kind=root-cause scope=debug id=a647d4feec27 created=2026-09-27T05:09:09 -->
### a647d4feec27 · root-cause · canonical_spec_ref is resolution-dependent, _folder_matches compares bytes

plan_ops.create stores refs.canonical_spec_ref(spec) in _meta.yaml (#697). canonical_spec_ref returns the value verbatim when it does not resolve (spec not written yet) and the bare filename once it does, so the same inputs yield different _meta.yaml bytes across the spec's creation, and _folder_matches' byte compare (minus created:) classifies the #133 finish-the-job re-run as a slug collision.

<!-- fr:journal kind=finding scope=debug id=f1-create-rerun created=2026-09-27T05:09:58 state=fixed -->
### f1-create-rerun · finding [fixed] · create re-run compares spec: by identity

plan_ops._folder_matches strips spec: from the byte compare and checks _same_spec (canonical_spec_ref of both); a matched re-run rewrites spec: canonically keeping the created: line. Tests: test_create_rerun_after_spec_is_written_appends_row_and_canonicalizes (red→green), test_create_rerun_with_a_different_spec_is_still_a_collision (guards #133).

<!-- fr:journal kind=repro scope=debug id=e922dcbd3800 created=2026-09-27T05:10:56 -->
### e922dcbd3800 · repro · single-plan archive leaves stale refs to a spec its own sweep moved

Plan B stranded in implemented/plans with spec: docs/superpowers/specs/y-design.md; y's row File cell docs/superpowers/plans/2026-09-03-b/. fr archive <plan A> moves y to implemented/specs but B's spec: stays the full active path (pre-#697 repaired it). Pinned by tests/unit/test_archive_cmd.py::test_single_plan_archive_repairs_refs_to_specs_its_own_sweep_moved (red).

<!-- fr:journal kind=root-cause scope=debug id=66db879b0aa6 created=2026-09-27T05:10:57 -->
### 66db879b0aa6 · root-cause · repair scope is the archived slugs, but the sweep's moves are repo-wide

archive_cmd passes only_plans={archived slugs} to both _report_sweep and the post-move repair_repo. spec_archive_sweep evaluates every spec under specs/, so it can move a spec whose plans are all other, earlier-archived plans; the refs that move made stale belong to those plans and fall outside only_plans.
