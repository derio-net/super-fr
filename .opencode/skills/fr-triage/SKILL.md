---
name: fr-triage
description: >
  Use when asked to triage, rank, prioritise or organise the open issues of a
  repo or of a whole org; when asked for a backlog board or "what should we
  work on next"; or when asked to refresh or sync an existing triage.
---

# fr-triage

**Announce at start:** "I'm using fr-triage to triage <repo or org>."

You can already read an issue, check it against the code and rank it. A triage done in chat dies with the session; `fr triage` keeps your ranking in a file, so a refresh costs only the delta.

## State: two files, two owners

Everything lives in `$HOME/.cache/fr/triage/<scope>/` (`owner--repo` for `--repo OWNER/REPO`, `owner` for
`--org OWNER`, lowercased; `--dir D` overrides). Pass the same `--repo`/`--org`/`--dir` to every command. `--repo A/B,C/D` is a **group** (owners may differ): one board, one directory (sorted `owner--repo` slugs joined by `+`, hashed past 80 characters), one `--max-inflight` cap. Two repos with the same name are refused (exit 2: keys are `<repo-name>#<n>`); batches stay single-repo; every repo of a group needs a `--checkout REPO=PATH`, even one with no batches (`batch drive` and a plan print without `--yes` are refused the same way).

| File | Written by | Holds |
|---|---|---|
| `facts.json` | `fr triage collect` | what the forge says: open issues, labels, linked PRs (no stages) |
| `judgements.yaml` | **you**, plus the `batch` verbs for `batches:` | tiers, per-issue rankings and `kind`, patterns, `features`, batches |
| `triage.html`, `snapshots/` | `fr triage render` | the board, built from both; a snapshot per render (latest 30), none if identical to the latest: a re-render keeps the diff against the last different one |

Stages (`backlog`, `blocked`, `in-progress`, `pr-draft`, `pr-ready`, `merged`, `closed`) are derived by `check` and `render`, never stored. Never set one, and never write facts yourself.

## The loop (a re-run of it is the sync)

1. **Collect.** `fr triage collect --repo OWNER/REPO` (or `--org OWNER`). If the **PR list** hit its limit, re-run
   once with `--pr-limit 1000`, then go on and report it; for an issue- or repo-list warning, say rows may be missing.
2. **Check.** `fr triage check --repo OWNER/REPO [--json]` prints these sets and always exits 0:
   - **unranked** / **unranked PRs**: open, with no judgement. Your work queue (PRs: see below).
   - **settled**: judged, now closed or merged. Report what shipped; keep the judgement.
   - **orphaned**: the key names no repo collect read (a typo'd or renamed repo). Fix the key, or remove it if
     the repo is gone. This is the only set you may act on without the forge.
   - **unreachable**: collect could not settle it; the reason is printed. Transient (rate limit, 5xx, lost
     access): **never prune on it**. "Judged after the last collect" means collect again; not-found is a deleted
     issue or typo'd number: confirm with `gh issue view`, then fix the number or recommend removing it.
   - **stale dispatch**: a batch dispatch with no PR after `stale_dispatch_days`. Report it.
   - **unplaced**: open, in no open batch, no `features` group and not `kind: parked` (a cancelled batch's members
     count). Place each: a batch, a feature group, or park it.
3. **Judge the unranked.** Read each from `facts.json` (bodies stop at 2,000 characters; `gh issue view` when cut
   off) and the code; a first run creates the file with `schema: 3` and `tiers`. Compare against ALL judgements.
4. **Render.** `fr triage render --repo OWNER/REPO --open` writes `triage.html` and a snapshot. The board reads: **Since last report**
   (the diff from the previous snapshot), **Needs you now** (computed, never typed: green drafts, failing CI, blocked batches,
   stale dispatches, unfinished `post_merge`, unplaced issues), **Next up** (the driver's own order), **Waves** (tabs, closing
   order, features, parked), then the backlog by tier. Report back the board's path, what changed, what needs the operator
   and the `gh` commands you recommend.
5. **Batch.** Propose groups of judged issues to ship as one run and one PR (`fr triage batch suggest` is input,
   never the answer); create the accepted ones with `fr triage batch create <id> --title T --issue KEY...`.

Open PRs are triaged in the same loop: each carries an intent anchor (closing issue, spec, debug journal, else
`unanchored`) with CI/merge badges. Judge the diff against it: `delivers | partial | drift | unanchored` plus one line
in `delivery_note`. Shallow by design: never a code review.
To sync later, run the same loop: `check` names what arrived, shipped or went missing.

## judgements.yaml

This file is your whole interface, and `fr triage --help` does not document it:

```yaml
schema: 3
ranked_at: 2026-09-21
tiers:                      # every tier an issue names must be declared here
  - n: 1
    title: "Data loss"
    description: "Work destroyed with no prompt or salvage."
issues:
  "super-fr#435":           # "<repo-name>#<n>" in both scopes; lowercase is canonical
    tier: 1
    theme: isolation
    cx: S                   # XS | S | S-M | M | L | "-" (quote it: a bare - is a YAML list)
    verified: true          # re-read at current main, not copied from the issue
    detail: "`gc()` trusts `MERGED` and calls `down()`. **Still live** on main (issue cites :1013, now :1312)."
    note: "Batch with super-fr#469, same subsystem."
    kind: defect            # optional: defect | feature | parked (parked = deliberately not now)
features:                   # optional ranked groups; "start" is shown, never run
  - rank: 1
    title: "Isolation GC"
    ids: ["super-fr#435"]
    why: "Data loss first"
    start: "/fr-goal ..."
patterns:
  - title: "Remote state justifies local destruction"
    ids: ["super-fr#435"]
batches:                    # written by the `batch` verbs; judged keys, one repo, one open batch
  - id: merged-trust        # a slug: [a-z][a-z0-9-]{0,39}
    title: "Stop trusting MERGED for local teardown"
    ids: ["super-fr#435"]   # optional: rationale, order, wave, after, bump (patch|minor|major), skill, launch
```

Quote every title, description, detail, note and body: a `: ` inside unquoted text, or a leading `-`, breaks the
file. Set `ranked_at` to today whenever you change a judgement. Keys are case-insensitive (two differing only by case conflict). `detail`, `note` and pattern `body` interpret only `` `code` `` and `**bold**`.
**Schema 3:** 1 and 2 still load; the first batch write upgrades the file. The engine appends each batch's `events:` (`dispatch`, `cancel`, `post_merge`, `closeout`): never write them; its stage is derived. `batch create|edit --wave N --after ID` set a wave and dependencies (an unknown id, self or a cycle is refused); only a `merged` dependency is met, and a cancelled, abandoned or partial one blocks. `batch dispatch` runs a batch as `/fr-goal` or `/fr-debugging` (its `skill`) on the launch model, else the harness's orchestrator binding, and marks its issues taken; `batch merge` merges batch PRs in order; `batch cancel` withdraws one.
**The driver:** `fr triage batch drive` runs the batches named, else those with a wave, else all, to completion: each pass merges every green non-draft batch PR (readying one stays the operator's), closes out each merged batch through its runner after the repo's `post_merge` argument list, merges its archive PR, and dispatches by wave up to `--max-inflight`. `--once` exits 0 acted or done, 3 waiting (blocked batches included: they need the operator), 2 refused; `--checkout REPO=PATH` names each clone; a second driver on the state directory is refused.

## The shape of a judgement

1. **Tier by what the failure costs**: lost work, then a failure that looks like success, then friction. Never
   by age, label, reporter or how loud the issue is.
2. **Verify against current main, at scale too.** Before `verified: true`, re-read the cited `file:line` at
   current main — snippets go stale, and at forty issues a fixed bug stays ranked as live. If you did not
   re-read it, write `verified: false`.
3. **Record line drift** in `detail` (`was :1013, now :1312`); a bug already fixed on main is a close
   recommendation, not a ranking.
4. **Hunt duplicates and batches.** Same predicate, same file, same sentence: link duplicates in `note`, and
   name the batch when issues share a subsystem. A shared root cause across three or more issues becomes a
   `patterns` entry.
5. **Forge actions are unrun commands.** A close, a dedupe or a relabel is the exact `gh` command in `note` or your
   report, for the operator to run. Never act on the forge unasked. `batch dispatch|merge|cancel|drive` act only
   with `--yes` (without it they print the plan; `drive` with no ids plans the batches with a wave, else all); pass
   `--yes` only when the operator asked for that action in this session.

## Privacy

The state directory is outside every repo on purpose. When the scope is outside the operator's own org, keep its
facts, judgements and board local — never in a commit, PR, journal or issue (`.claude/rules/third-party-privacy.md`).
