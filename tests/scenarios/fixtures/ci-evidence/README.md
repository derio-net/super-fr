# `ci-evidence` — the scenario's forge, captured

Captured live on 2026-10-08 from a Claude Code cloud session with `gh api`
against `derio-net/super-fr` (draft PR 1088, this feature's own PR), stdout byte
for byte:

- `pulls-by-head.json` — `gh api 'repos/derio-net/super-fr/pulls?head=derio-net:feat/cloud-triage&state=all&per_page=100&page=1'`
- `pull-1088.json` — `gh api repos/derio-net/super-fr/pulls/1088`

`bin/gh` serves these, plus the check-run moments under
`tests/fixtures/github_rest/commit_checks/` and PR 852's captured files page.
