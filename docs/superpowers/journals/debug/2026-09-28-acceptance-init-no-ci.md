# Journal: 2026-09-28-acceptance-init-no-ci

<!-- fr:journal kind=repro scope=debug id=ab1fd4edd78e created=2026-09-28T19:00:39+00:00 -->
### ab1fd4edd78e · repro · init on a GitLab repo with no CI scaffolds .gitlab-ci.yml and rewrites .gitignore

Scratch repo, origin on gitlab.com (example-org/demo), .gitignore without a trailing newline, no CI config. `fr acceptance init` creates .gitlab-ci.yml (installing fr from GitHub main), the matrix header names .github/workflows, and .gitignore is rewritten via splitlines()+join (whole-file normalization: final newline added, CRLF would become LF). `fr acceptance set-status --status ci` has no gate at all — any row moves to ci with any evidence.
