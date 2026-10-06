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
     count). Place each: a batch, a feature group, or park it. A judged duplicate is never listed here.
   - **duplicate candidates**: groups of open issues the engine proposes as duplicates, each flagged pair with its
     reasons (close titles, shared rare identifiers, a shared finding id and issue reference, same theme). A
     proposal, not a verdict: judge every group (step 3).
   - **duplicates**: every open issue judged `duplicate_of` an original, with the original's state (`open`,
     `closed` or `missing`) and, for an open or closed one, the exact `gh issue close N --repo OWNER/REPO
     --duplicate-of <url>` command. Report those commands to the operator; never run them. A `missing` original
     prints no command and names why: fix the key, or collect again.
3. **Judge the unranked.** Read each from `facts.json` (bodies stop at 2,000 characters; `gh issue view` when cut
   off) and the code; a first run creates the file with `schema: 3` and `tiers`. Compare against ALL judgements.
   Then judge each **duplicate candidate** group: re-read its issues, and set `duplicate_of: <original>` on each
   duplicate (the original is the issue with the fuller evidence, else the older one), or `distinct_from: [<other>]`
   when they differ, so the pair is not proposed again.
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
  "super-fr#470":           # a judged duplicate: nested under its original on the board
    tier: 1
    duplicate_of: "super-fr#435"      # one original, itself not a duplicate (no chains); never itself
    distinct_from: ["super-fr#469"]   # keys judged NOT duplicates of this one; each once, never the same key as duplicate_of
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
**The driver:** `fr triage batch drive` runs the batches named, else those with a wave, else all, to completion: each pass treats a repo's ready PRs as a merge train: only the head of them (wave, then order, then id) is merged or, when behind its base, updated, the next one follows in the same pass once the head merged, and a failing or refused PR is stepped over; every pass prints a `train` line per repo and `queued N` for the members it did not attempt (readying a PR stays the operator's; a batch PR, or an archive PR, is one from the repo itself by an allowed author: `pr_authors` in `.fr/triage.yaml`, default the authenticated user, so a fork or foreign-author PR on a batch branch is never merged, only reported once and listed under Needs you now). It closes out each merged batch through its runner after the repo's `post_merge` argument list, merges its archive PR, and dispatches by wave up to `--max-inflight`. In loop mode it also prints one `dedupe` line when it sees a wave go
from unfinished to finished while duplicate candidates exist: the count and the `fr triage check` command to judge them (it never judges or writes a duplicate; a wave already finished at start, and `--once`, report nothing). Each wave's sessions open in a herdr workspace of their own, `<prefix>-wave-<n>` (`<prefix>-no-wave` for a batch with no wave; `--workspace-prefix`, default `drive`); once a batch is finished (its archive PR merged) its batch and close-out sessions are closed, never one still working or blocked (it is retried next pass), and a wave workspace its last session empties closes with it; `--keep-sessions` leaves them open, and closing never changes an exit code. `--once` exits 0 acted or done, 3 waiting (blocked batches included: they need the operator), 2 refused; in loop mode a failed or timed-out forge read (each `gh` call is bounded) skips the pass, is reported once, and is read again after `--interval`; `--checkout REPO=PATH` names each clone; a second driver on the state directory is refused. A batch closed out by hand is recorded once as a `closeout` event and never closed out again: either its run is archived, or a PR from the repo itself by an allowed author is open or merged on `chore/closeout-<batch branch>`; an open one is then merged like any other archive PR.

**The board:** `fr triage board` writes `board.html` beside `triage.html`: a live Kanban of the batches in six lifecycle columns, each card showing its session status and a copyable jump command (`--refresh N` reloads the page every N seconds, default 30; `--open` opens it). Every `--yes` pass of `drive` re-renders it, so while a driver runs it stays fresh on its own; with no driver, `fr triage board --watch [--interval N]` re-collects and re-renders until interrupted (refused while a live drive holds the lock). `fr triage batch focus <id> [--closeout]` switches the terminal to a batch's live session through the runner that dispatched it. Once `board.html` exists, `fr triage render` links it from the Batches section.

## The shape of a judgement

1. **Tier by what the failure costs**: lost work, then a failure that looks like success, then friction. Never
   by age, label, reporter or how loud the issue is.
2. **Verify against current main, at scale too.** Before `verified: true`, re-read the cited `file:line` at
   current main — snippets go stale, and at forty issues a fixed bug stays ranked as live. If you did not
   re-read it, write `verified: false`.
3. **Record line drift** in `detail` (`was :1013, now :1312`); a bug already fixed on main is a close
   recommendation, not a ranking.
4. **Hunt duplicates and batches.** Same predicate, same file, same sentence: record a duplicate in the
   structured `duplicate_of` field (or `distinct_from` for a pair that only looks alike), never as prose in
   `note`, and name the batch when issues share a subsystem. A shared root cause across three or more issues becomes a
   `patterns` entry.
5. **Forge actions are unrun commands.** A close, a dedupe (`gh issue close N --duplicate-of <url>`, which `check`
   prints for every judged duplicate) or a relabel is the exact `gh` command in `note` or your
   report, for the operator to run. Never act on the forge unasked. `batch dispatch|merge|cancel|drive` act only
   with `--yes` (without it they print the plan; `drive` with no ids plans the batches with a wave, else all); pass
   `--yes` only when the operator asked for that action in this session.

## Privacy

The state directory is outside every repo on purpose. When the scope is outside the operator's own org, keep its
facts, judgements and board local — never in a commit, PR, journal or issue (`.claude/rules/third-party-privacy.md`).
