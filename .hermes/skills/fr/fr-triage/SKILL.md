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
lacks is everything around that: the result dies with the session, syncs are invisible, and a
refresh means doing it all again. `fr triage` fixes that. Your ranking goes into a file, never only into chat.

## State: two files, two owners

Everything lives in one state directory, `$HOME/.cache/fr/triage/<scope>/` (`owner--repo`
for `--repo OWNER/REPO`, `owner` for `--org OWNER`, lowercased; `--dir D` overrides).
Pass the same `--repo`/`--org`, and `--dir` if you use it, to every command.

| File | Written by | Holds |
|---|---|---|
| `facts.json` | `fr triage collect` | what the forge says: open issues, labels, linked PRs (no stages) |
| `judgements.yaml` | **you** | tiers, per-issue rankings, patterns |
| `triage.html` | `fr triage render` | the board, built from both |

Stages (`backlog`, `blocked`, `pr-draft`, `pr-ready`, `merged`, `closed`) are derived by `check` and `render`, never stored. Never set one, and never write facts yourself.

## The loop (a re-run of it is the sync)

1. **Collect.** `fr triage collect --repo OWNER/REPO` (or `--org OWNER`). If it warns that the
   **PR list** hit its limit, re-run once with `--pr-limit 1000`; if it still warns, go on and say
   so in your report. An issue- or repo-list warning has no flag: go on, and say rows may be missing.
2. **Check.** `fr triage check --repo OWNER/REPO [--json]` prints five sets and always exits 0:
   - **unranked**: open, with no judgement. This is your work queue.
   - **unranked PRs**: open PRs with no judgement. Triaged in the same loop (see below).
   - **settled**: judged, now closed or merged. Report what shipped; keep the judgement.
   - **orphaned**: the key names no repo collect read (a typo'd or renamed repo). Fix the key,
     or remove it if the repo is gone. This is the only set you may act on without the forge.
   - **unreachable**: collect could not settle it, and the reason is printed. Transient
     (rate limit, 5xx, lost access): **never prune on it**. "Judged after the last collect"
     means collect again; a not-found reason is a deleted issue or typo'd number — confirm
     with `gh issue view`, then fix the number or recommend removing it.
3. **Judge the unranked.** Read each from `facts.json` (bodies stop at 2,000 characters;
   use `gh issue view` when cut off) and the code; on a first run, create the file with
   `schema: 1` and your `tiers` first. Compare every new issue against ALL judgements.
4. **Render.** `fr triage render --repo OWNER/REPO --open` writes `triage.html` and opens it.
   Unranked issues render first, so an incomplete triage is visible on the board itself.

Open PRs are triaged in the same loop: `check` reports unranked PRs alongside
unranked issues. Each carries an intent anchor (closing issue, then spec, then
debug journal, else `unanchored`) with CI/merge badges. Judge the diff against
the anchor — `delivers | partial | drift | unanchored` plus one line in
`delivery_note`. Shallow by design: never a code review.

To sync later, run the same loop. `check` names exactly what arrived, shipped or could not be found since the last triage, so a refresh costs the delta, not the backlog.

## judgements.yaml

This file is your whole interface, and `fr triage --help` does not document it:

```yaml
schema: 1
ranked_at: 2026-09-21
tiers:                      # every tier an issue names must be declared here
  - n: 1
    title: "Data loss"
    description: "Work destroyed with no prompt or salvage."
  - n: 2
    title: "Silent wrongness"
    description: "The failure looks like success."
issues:
  "super-fr#435":           # "<repo-name>#<n>" in both scopes; lowercase is canonical
    tier: 1
    theme: isolation
    cx: S                   # XS | S | S-M | M | L | "-" (quote it: a bare - is a YAML list)
    verified: true          # re-read at current main, not copied from the issue
    detail: "`gc()` trusts `MERGED` and calls `down()`. **Still live** on main (issue cites :1013, now :1312)."
    note: "Batch with super-fr#469, same subsystem."
patterns:
  - title: "Remote state justifies local destruction"
    ids: ["super-fr#435"]
    body: "…"
```

Keep this block style and quote every title, description, detail, note and body: a `: `
inside unquoted text, or a leading `-`, breaks the file. Set `ranked_at` to today whenever you
add or change a judgement; the board shows it. Keys are
case-insensitive, so two keys differing only by case are refused as a conflict.
`detail`, `note` and pattern `body` interpret exactly two inline forms, `` `code` `` and
`**bold**`; everything else is shown as literal text.

## The shape of a judgement

1. **Tier by what the failure costs**: lost work, then a failure that looks like success, then
   friction. Never by age, label, reporter or how loud the issue is.
2. **Verify against current main, at scale too.** Before `verified: true`, re-read the cited
   `file:line` at current main — snippets go stale, and at forty issues a fixed bug stays
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

After render, tell the operator the board's path and the delta: newly judged, settled,
orphaned/unreachable, and the handful of `gh` commands you recommend. The board holds the ranking.

## Privacy

The state directory is outside every repo on purpose. When the scope is outside the
operator's own org, keep its facts, judgements and board local — never into a commit,
PR, journal or issue (`.claude/rules/third-party-privacy.md`).
