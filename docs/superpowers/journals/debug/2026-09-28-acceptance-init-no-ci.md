# Journal: 2026-09-28-acceptance-init-no-ci

<!-- fr:journal kind=repro scope=debug id=ab1fd4edd78e created=2026-09-28T19:00:39+00:00 -->
### ab1fd4edd78e · repro · init on a GitLab repo with no CI scaffolds .gitlab-ci.yml and rewrites .gitignore

Scratch repo, origin on gitlab.com (example-org/demo), .gitignore without a trailing newline, no CI config. `fr acceptance init` creates .gitlab-ci.yml (installing fr from GitHub main), the matrix header names .github/workflows, and .gitignore is rewritten via splitlines()+join (whole-file normalization: final newline added, CRLF would become LF). `fr acceptance set-status --status ci` has no gate at all — any row moves to ci with any evidence.

<!-- fr:journal kind=hypothesis scope=debug id=0a8f1bb010d4 created=2026-09-28T19:00:40+00:00 -->
### 0a8f1bb010d4 · hypothesis · acceptance's CI-shaped outputs key off the forge backend, never off whether CI exists

scaffold.init(backend) picks the CI file from detect_backend (the forge); nothing checks for an existing CI config. set_status_cmd validates only the Status literal. Same missing fact (does this repo have CI?) behind the CI file and the ci status.
