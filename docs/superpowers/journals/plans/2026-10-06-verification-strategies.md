# Journal: 2026-10-06-verification-strategies

<!-- fr:journal kind=decision scope=plan id=p1-shared-shipped-walk created=2026-10-06T11:28:03+00:00 phase=1 -->
### p1-shared-shipped-walk · decision · shared shipped-dir walk lives in fr/_shipped.py; workflow keeps its own packaged_shipped_workflows_dir (phase 1)

fr/_shipped.py holds packaged_dir(dirname), shipped_dirs, lookup_candidates, listing and MARKETPLACE_ROOT (re-exported from workflow.resolve). workflow.resolve keeps a thin packaged_shipped_workflows_dir wrapper because tests monkeypatch it by that name. The packaged-dir cache moved from two module globals to a per-dirname dict.

<!-- fr:journal kind=decision scope=plan id=p1-strategy-template-shape created=2026-10-06T11:28:03+00:00 phase=1 -->
### p1-strategy-template-shape · decision · install/scenario accept a string (shell-split) or a list, stored as tuple; check_workflow takes optional repo_root (phase 1)

StrategyManifest.install/scenario normalise to tuple[str,...] | None. check_workflow(manifest, repo_root=None) resolves `verification:` against shipped sources only when repo_root is None; the CLI passes the repo root. resolve_strategy accepts repo_root=None for the same reason. effective_strategy(row_verify, row_id, section, shape_default) and is_post_merge(strategy, repo_root) take plain strings per the plan; is_post_merge raises StrategyError on an unresolvable name. spec_section ignores prose and fenced code, and errors only on a bullet or strategy: line that breaks the grammar; the reason is optional in the grammar (self-review owns 'reason owed').

<!-- fr:journal kind=discovery scope=plan id=p1-no-change-fragment created=2026-10-06T11:28:03+00:00 phase=1 -->
### p1-no-change-fragment · discovery · no .changes fragment added in phase 1 (phase 1)

This phase touches packages/*/src and plugins/*/workflows, so the PR needs a .changes/<branch-slug>.yaml fragment; none was in this phase's steps. It is owed before delivery.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-06T11:28:03+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the task's GREEN step is itself the refactor (the four-place walk factored into fr/_shipped.py, workflow/resolve.py re-pointed, behaviour pinned by the unchanged workflow tests); nothing further to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-06T11:28:03+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

data-only task: four manifests plus a byte copy; no code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-06T11:28:03+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

thin CLI mirroring workflow_cmd.py and one optional field; nothing duplicated worth extracting

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-10-06T11:28:03+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

two small pure functions written once against their tests; nothing to clean
