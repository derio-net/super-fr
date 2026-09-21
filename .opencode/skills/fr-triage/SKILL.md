---
name: fr-triage
description: >
  Use when asked to triage, rank, prioritise or organise the open issues of a
  repo or of a whole org; when asked for a backlog board or "what should we
  work on next"; or when asked to refresh or sync an existing triage.
---

# fr-triage

**Announce at start:** "I'm using fr-triage to triage <repo or org>."

You can already read an issue, check it against the code and rank it. What a triage done in chat
lacks is everything around that: the result dies with the session, the next triage cannot tell
what changed since this one, and a sync means doing it all again. `fr triage` fixes those three
things. Route every triage through it. Your ranking goes into a file, never only into chat.

## State: two files, two owners

Everything lives in one state directory, `$HOME/.cache/fr/triage/<scope>/`, where scope is
`owner--repo` for `--repo OWNER/REPO` or `owner` for `--org OWNER`, lowercased (`--dir D`
overrides it).

| File | Written by | Holds |
|---|---|---|
| `facts.json` | `fr triage collect` | what the forge says: open issues, linked PRs, derived stages |
| `judgements.yaml` | **you** | tiers, per-issue rankings, patterns |
| `triage.html` | `fr triage render` | the board, built from both |

Stages (`backlog`, `blocked`, `pr-draft`, `pr-ready`, `merged`, `closed`) are derived from the
forge on every collect. Never set one, and never write facts yourself.

## The loop (a re-run of it is the sync)

1. **Collect.** `fr triage collect --repo OWNER/REPO` (or `--org OWNER`). If it warns that a list
   returned exactly its limit, re-run with a larger `--pr-limit` before judging anything.
2. **Check.** `fr triage check --repo OWNER/REPO [--json]` prints four sets and always exits 0:
   - **unranked**: open, with no judgement. This is your work queue.
   - **settled**: judged, now closed or merged. Report what shipped; keep the judgement.
   - **orphaned**: a judgement whose issue the forge no longer has (deleted, or a typo'd key).
     The only candidate for removal, and only after you confirm the key is not a typo.
   - **unreachable**: the forge failed to answer, or the repo was skipped. **Never prune an
     unreachable judgement.** It is a transient failure, not a verdict.
3. **Judge the unranked.** Read each one from `facts.json` and the code, and add it to
   `judgements.yaml`. Leave existing judgements alone unless their facts changed.
4. **Render.** `fr triage render --repo OWNER/REPO --open` writes `triage.html` and opens it.
   Unranked issues render first, so an incomplete triage is visible on the board itself.

To sync later, run the same loop. `check` names exactly what arrived, shipped or vanished since
the last triage, so a refresh costs the delta, not the backlog.

## judgements.yaml

This file is your whole interface, and `fr triage --help` does not document it:

```yaml
schema: 1
ranked_at: 2026-09-21
tiers:                      # every tier an issue names must be declared here
  - {n: 1, title: Data loss, description: Work destroyed with no prompt or salvage.}
  - {n: 2, title: Silent wrongness, description: The failure looks like success.}
issues:
  "super-fr#435":           # "<repo-name>#<n>" in both scopes; lowercase is canonical
    tier: 1
    theme: isolation
    cx: S                   # XS | S | S-M | M | L | -
    verified: true          # re-read at current main, not copied from the issue
    detail: "`gc()` trusts `MERGED` and calls `down()`. **Still live** on main (issue cites :1013, now :1312)."
    note: "Batch with super-fr#469, same subsystem."
patterns:
  - {title: Remote state justifies local destruction, ids: ["super-fr#435"], body: "…"}
```

Keys are case-insensitive, so two keys differing only by case are refused as a conflict.
`detail`, `note` and pattern `body` interpret exactly two inline forms, `` `code` `` and
`**bold**`; everything else is shown as literal text.

## The shape of a judgement

1. **Tier by what the failure costs**: lost work, then a failure that looks like success, then
   friction. Never by age, label, reporter or how loud the issue is.
2. **Verify against current main, at scale too.** Before `verified: true`, re-read the cited
   `file:line` at current main. Issue snippets go stale and line numbers move, and the pressure to
   trust a quoted snippet grows with the backlog: at forty issues it is how a fixed bug stays
   ranked as live. If you did not re-read it, write `verified: false`.
3. **Record line drift** in `detail` when a cited line moved (`was :1013, now :1312`), and say
   when the bug is already fixed on main: that is a close recommendation, not a ranking.
4. **Hunt duplicates and batches.** Same predicate, same file, same sentence: link duplicates in
   `note`, and name the batch when issues share a subsystem. A shared root cause across three or
   more issues becomes a `patterns` entry.
5. **Forge actions are unrun commands.** A close, a dedupe or a relabel is written as the exact
   `gh` command in `note` or in your report, for the operator to run. Never act on the forge
   unasked.

## Report back

After render, tell the operator the board's path and the delta: how many issues were unranked
and are now judged, what settled, anything orphaned or unreachable, and the handful of forge
commands you recommend. Do not paste the whole ranking into chat; the board holds it.

## Privacy

The state directory is outside every repo on purpose. When the scope is an org outside the
operator's own, keep its facts, judgements and board local. Never copy them into a commit, a PR,
a journal or an issue (`.claude/rules/third-party-privacy.md`).
