<!-- fr:journal-schema=4 -->
# Journal: 2026-11-13-placement-emitted-paths

<!-- fr:journal kind=repro scope=debug id=a432b367799e created=2026-11-13T20:50:47+00:00 -->
### a432b367799e · repro · quiet/stealth: run resolve --emitted spec= refused in every spelling

tests/unit/test_placement_emitted_paths.py: under quiet, after run start, a spec written at <fr worktree>/features/feat__q/docs/superpowers/specs/x.md cannot be recorded by fr run resolve --step brainstorm --state done --emitted spec=...: the logical docs/superpowers/... and the features/<id>/... spellings are 'does not exist' (looked under the product workspace), the absolute path is 'outside the repo'. _repo_relative_artifact (run_cmd.py) judges against the product root only.
