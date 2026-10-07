# gh CLI fixtures

Captured live 2026-10-06 (gh, against `derio-net/super-fr`) for batch adopt's PR
supersede (spec 2026-10-06-triage-batch-adopt §C). A scratch branch
`scratch/fr-adopt-capture` holding one empty commit on `origin/main` was pushed,
then, in order:

- `pr-create-draft.stdout` — stdout of `gh pr create --repo derio-net/super-fr
  --head scratch/fr-adopt-capture --base main --title … --body … --draft`
  (stderr was empty): the PR URL on one line.
- `pr-view-adopt.json` — stdout of `gh pr view 1044 --repo derio-net/super-fr
  --json number,title,body,isDraft,baseRefName,headRefName,state,url`, taken
  after the close below (hence `CLOSED`).
- `pr-close.stderr` — stderr of `gh pr close 1044 --repo derio-net/super-fr`
  (stdout was empty, exit 0).
- `gh api -X DELETE repos/derio-net/super-fr/git/refs/heads/scratch/fr-adopt-capture`
  printed nothing on either stream (exit 0), so it has no fixture file.

PR #1044 was closed and its branch deleted straight away. Nothing redacted: every
name is `derio-net`'s own.
