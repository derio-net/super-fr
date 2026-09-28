# Journal: 2026-09-28-acceptance-init-no-ci

<!-- fr:journal kind=repro scope=debug id=ab1fd4edd78e created=2026-09-28T19:00:39+00:00 -->
### ab1fd4edd78e · repro · init on a GitLab repo with no CI scaffolds .gitlab-ci.yml and rewrites .gitignore

Scratch repo, origin on gitlab.com (example-org/demo), .gitignore without a trailing newline, no CI config. `fr acceptance init` creates .gitlab-ci.yml (installing fr from GitHub main), the matrix header names .github/workflows, and .gitignore is rewritten via splitlines()+join (whole-file normalization: final newline added, CRLF would become LF). `fr acceptance set-status --status ci` has no gate at all — any row moves to ci with any evidence.

<!-- fr:journal kind=hypothesis scope=debug id=0a8f1bb010d4 created=2026-09-28T19:00:40+00:00 -->
### 0a8f1bb010d4 · hypothesis · acceptance's CI-shaped outputs key off the forge backend, never off whether CI exists

scaffold.init(backend) picks the CI file from detect_backend (the forge); nothing checks for an existing CI config. set_status_cmd validates only the Status literal. Same missing fact (does this repo have CI?) behind the CI file and the ci status.

<!-- fr:journal kind=root-cause scope=debug id=4b8a243cbdaa created=2026-09-28T19:04:52+00:00 -->
### 4b8a243cbdaa · root-cause · A: CI outputs key off the forge backend, never off whether the repo has CI

scaffold.init picks the pipeline file from detect_backend (the forge) and writes it unconditionally; the matrix header and rule hard-code .github/workflows. The record engine's _acceptance_writes (the one path behind add/set-status/resolve --record) validates only the Status literal, so any row reaches `ci` in a repo with no CI.

<!-- fr:journal kind=root-cause scope=debug id=1f74045b4b19 created=2026-09-28T19:04:53+00:00 -->
### 1f74045b4b19 · root-cause · B: init rewrites .gitignore wholesale

splitlines()+join+'\n' normalises the final newline and CRLF→LF, so the diff is larger than the one line and reverting that line still leaves the worktree dirty (the stray edit that blocked `isolation down`). Operator confirmed: two causes, fix both in one PR; `ci` gate = a CI config exists for the backend.

<!-- fr:journal kind=finding scope=debug id=1ba19b3ddc46 created=2026-09-28T19:19:07+00:00 state=fixed -->
### 1ba19b3ddc46 · finding [fixed] · init scaffolds CI only beside existing CI; `ci` needs a CI config; .gitignore append-only

fr/acceptance/ci.py (ci_config, one detector); scaffold.init(with_ci=) + templates parametrised on the CI line; record/apply.py refuses a move INTO `ci` without CI (rows already ci untouched); _append_gitignore_line byte-exact. Failing-test-first: tests/unit/test_acceptance_init_no_ci.py (7 red → 15 green). Existing init tests now pass --with-ci where they pin the workflow's shape; make_repo gains ci=True.

<!-- fr:journal kind=review scope=debug id=010adc6378c9 created=2026-09-28T19:32:50+00:00 -->
### 010adc6378c9 · review · Independent adversarial review: no findings at the fix-now bar

Verified: _acceptance_writes is the only production caller of insert_row/replace_row (no gate bypass); refusal fires before any overlay write; GitHub-with-CI templates byte-identical to origin/main; tests fail on revert. Below the bar, not fixed: CR-only .gitignore files and a trailing-space variant of the line are not recognised as present (a harmless duplicate line); ci_config accepts any workflow, not specifically the acceptance job — the known simplification gh#774's declared ci service replaces.
