# Gitea API fixtures — captured live

Captured 2026-11-01 from a self-hosted Gitea (instance address redacted to
`gitea.example.com:3000`, login redacted to `walker`, email and avatar hash
blanked) with `tea` 0.16.0, against a private scratch repo created and
deleted for the Phase 9 walk of
`2026-07-09-multi-backend-git-host-adapters`.

Each `<name>.json` is the body `tea api -i <endpoint>` printed on stdout and
`<name>.status` is the HTTP status line `-i` wrote to stderr. `tea api`
exits 0 whatever that status is — the `.status` files are the only error
signal, which is what `fr.tea.api_json` reads.

The instance's `ROOT_URL` is plain `http://`, so every `html_url` here is
`http://…` — a real shape for a LAN-hosted Gitea, kept on purpose.

| file | endpoint |
|---|---|
| `repo` | `/repos/{owner}/{repo}` |
| `user` | `/user` |
| `labels` | `/repos/{owner}/{repo}/labels?limit=50&page=1` — two labels share a name: Gitea allows it |
| `contents_root` / `contents_readme` / `contents_missing` | `/repos/{owner}/{repo}/contents/…` (the last is a 404) |
| `pulls_all` / `pull_2` / `pull_missing` | `/repos/{owner}/{repo}/pulls…` (merged PR #2; the last is a 404) |
| `issues_all` | `/repos/{owner}/{repo}/issues?state=all&type=issues&limit=50&page=1` |
| `issues_page_empty` | page 2 of the same listing — Gitea's end-of-pages signal is `[]` |
| `issue_1_timeline` | `/repos/{owner}/{repo}/issues/1/timeline` — PR #2 and plain issue #3 both reference #1 |

Re-capture with the walk's `capture_gitea.sh` (not committed: it needs a live
instance); never hand-edit a body — redact by rule, as above.
