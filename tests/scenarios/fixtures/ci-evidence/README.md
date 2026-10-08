# `ci-evidence` — the scenario's forge, captured

Captured live on 2026-10-08 from a Claude Code cloud session with `gh api`
against `derio-net/super-fr` (draft PR 1088, this feature's own PR), stdout byte
for byte:

- `pull-1088.json` — `gh api repos/derio-net/super-fr/pulls/1088`

`bin/gh` serves it, plus the open-PR lookup
(`pulls?head=derio-net:feat/cloud-triage&state=open`) and the check-run moments
`green-head` and `pending`, all captured under `tests/fixtures/github_rest/`
(that directory's README). It serves no files page: the open-PR lookup reads
none (review finding p2-r7), and a request for one fails the scenario.
