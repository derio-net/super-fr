<!-- fr:journal-schema=4 -->
# Journal: 2026-11-13-placement-emitted-paths

<!-- fr:journal kind=repro scope=debug id=a432b367799e created=2026-11-13T20:50:47+00:00 -->
### a432b367799e · repro · quiet/stealth: run resolve --emitted spec= refused in every spelling

tests/unit/test_placement_emitted_paths.py: under quiet, after run start, a spec written at <fr worktree>/features/feat__q/docs/superpowers/specs/x.md cannot be recorded by fr run resolve --step brainstorm --state done --emitted spec=...: the logical docs/superpowers/... and the features/<id>/... spellings are 'does not exist' (looked under the product workspace), the absolute path is 'outside the repo'. _repo_relative_artifact (run_cmd.py) judges against the product root only.

<!-- fr:journal kind=root-cause scope=debug id=rc-emitted created=2026-11-13T20:59:00+00:00 -->
### rc-emitted · root-cause · emitted spec/plan judged against the product root, not the artifact root

_repo_relative_artifact resolved --emitted against the product checkout; under quiet/stealth the spec lives below the feature root (fr.artifacts.paths.feature_root). The cursor's convention (verification/exit.py already reads artifact_root / plan_rel) is artifact-root-relative, so the writer was the outlier, and ~12 readers joined the product root too (run_cmd plan/spec reads, record template/pr_body/apply, verification set/rows, ops holds, run visual/adopt, ops_cmd, cli-step {{ artifacts.* }} rendered for a cwd of the product checkout). Second layer: Plan.repo_root is the git toplevel of the plan dir (the fr worktree), so a quiet plan never resolved its spec and fr pickup matched features/<id>/docs/... against the recorded docs/...
