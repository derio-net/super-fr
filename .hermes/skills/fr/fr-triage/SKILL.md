---
name: fr-triage
description: >
  Use when asked to triage, rank, prioritise or organise the open issues of a
  repo or of a whole org; when asked for a backlog board or "what should we
  work on next"; or when asked to refresh or sync an existing triage.
---

# fr-triage

**Announce:** "I'm using fr-triage to triage <repo or org>." You rank issues; `fr triage` keeps your ranking in a file.

## Pages and state

Four pages, one question each: the backlog page `triage.html` (`fr triage render`: what do I do next?), origins (`fr triage origins render`), architecture (`fr triage architecture render`) and history (`fr triage history render`: how did we get here?). Hand-written analysis lives in fragments listed in `<state>/<page>/manifest.yaml`, never in an edited page; the dirs are `board/` (for `triage.html`, not the Kanban `board.html`), `origins/`, `architecture/` and `history/`. `fr triage state export --to <dir>` / `import --from <dir>` copy the durable state to and from a repo; `export: {path: <dir>}` in `.fr/triage.yaml` makes `batch drive` export finished waves (see **The driver**).

Everything lives in `$HOME/.cache/fr/triage/<scope>/` (`owner--repo` for `--repo OWNER/REPO`, `owner` for `--org OWNER`, lowercased). `--repo A/B,C/D` is a group; two repos with same name are refused (keys are `<repo-name>#<n>`); batches stay single-repo.

| File | Written by | Holds |
|---|---|---|
| `facts.json` | `fr triage collect` | forge data: issues, labels, PRs |
| `judgements.yaml` | **you**, plus `batch` verbs | tiers, rankings, `kind`, patterns, batches |
| `triage.html`, `board.html` | `fr triage render`, `fr triage board` | the backlog page and its latest 30 snapshots; the batch Kanban |

Stages are derived by `check` and `render`, never stored. Never write facts yourself.

## The loop (a re-run of it is the sync)

1. **Collect.** `fr triage collect --repo OWNER/REPO` (or `--org OWNER`). If the **PR list** hit its limit, re-run once with `--pr-limit 1000`, then go on and report it; for an issue- or repo-list warning, say rows may be missing.
2. **Check.** `fr triage check --repo OWNER/REPO [--json]` prints these sets and always exits 0:
   - **unranked** / **unranked PRs**: open, with no judgement. Your work queue (PRs: see below).
   - **settled**: judged, now closed or merged. Report what shipped; keep the judgement.
   - **orphaned**: the key names no repo collect read (a typo'd or renamed repo). Fix the key, or remove it if
     the repo is gone. This is the only set you may act on without the forge.
   - **unreachable**: collect could not settle it; the reason is printed. Transient (rate limit, 5xx, lost
     access): **never prune on it**. "Judged after the last collect" means collect again; not-found is a deleted
     issue or typo'd number: confirm on the forge (on GitHub, `gh issue view`), then fix the number or recommend removing it.
   - **stale dispatch**: a batch dispatch with no PR after `stale_dispatch_days`. Report it.
   - **awaiting live**: open issues carrying `fr:awaiting-live` (a merged PR only `Refs`'d them: a post-merge walk is still owed). Their own set (`awaiting_live` in `--json`), never ranked, proposed, unranked or unplaced; the board shows them in a group of their own, and a batch whose open members ALL await live is held (no Next up row, holds no wave open). The operator closes one once the walk is recorded (`fr acceptance set-status --walk` prints the command).
   - **unplaced**: open, in no open batch, no `features` group and not `kind: parked` (a cancelled batch's members
     count). Place each: a batch, a feature group, or park it; a judged duplicate is never listed. **no severity**: open and judged, no `severity`; set one. **duplicate target unknown** / **duplicate chained**: a `duplicate_of` the forge would not show, or one naming another duplicate; fix the key.
   - **duplicate candidates**: groups of open issues the engine proposes as duplicates, each pair with its reasons (close titles, shared rare identifiers, a shared finding id and issue reference, same theme). A proposal, not a verdict: judge every group (step 3). **duplicates**: each open issue judged `duplicate_of`, with its original's state (`open`, `closed`, `missing`) and, unless missing, the exact close command (on GitHub, `gh issue close N --repo OWNER/REPO --duplicate-of <url>`): report it to the operator, never run it.
3. **Judge the unranked.** Read each from `facts.json` (bodies stop at 2,000 characters; read the issue on the forge when cut
   off: on GitHub, `gh issue view`) and the code; a first run creates the file with `schema: 3` and `tiers`. Compare against ALL judgements.
   Then judge each **duplicate candidate** group: re-read its issues, and set `duplicate_of: <original>` on each duplicate (the original is the issue with the fuller evidence, else the older one), or `distinct_from: [<other>]` when they differ, so the pair is not proposed again.
4. **Render.** `fr triage render --repo OWNER/REPO --open` writes `triage.html` and a snapshot. The board reads: **Since last report**
   (the diff from the previous snapshot), **Needs you now** (computed, never typed: green drafts, failing CI, blocked batches,
   stale dispatches, unfinished `post_merge`, unplaced issues), **Next up** (the driver's own order), **Waves** (tabs, closing
   order, features, parked), then the backlog by tier. Report back the board's path, what changed, what needs the operator
   and the forge commands you recommend (on GitHub, `gh …`).
5. **Batch.** Propose groups of judged issues to ship as one run and one PR (`fr triage batch suggest` is input,
   never the answer); create the accepted ones with `fr triage batch create <id> --title T --issue KEY...`.

Open PRs are triaged in the same loop: each carries an intent anchor (closing issue, spec, debug journal, else `unanchored`) with CI/merge badges. Judge the diff against it: `delivers | partial | drift | unanchored` plus one line in `delivery_note`. Shallow by design: never a code review.
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
    severity: high          # optional: low | med | high
    duplicate_of: "super-fr#400"  # optional: listed under Parked as "duplicate of", counts as placed
    verified: true          # re-read at current main, not copied from the issue
    detail: "`gc()` trusts `MERGED` and calls `down()`. **Still live** on main (issue cites :1013, now :1312)."
    note: "Batch with super-fr#469, same subsystem."
    kind: defect            # optional: defect | feature | parked (parked = deliberately not now)
  "super-fr#470": {tier: 1, duplicate_of: "super-fr#435", distinct_from: ["super-fr#469"]}  # original (never a duplicate itself, no chains); keys judged NOT duplicates, each once
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
**The driver:** `fr triage batch drive` runs the batches named, else those with a wave, else all, to completion: each pass treats a repo's ready PRs as a merge train: only the head of them (wave, then order, then id) is merged or, when behind its base, updated, the next one follows in the same pass once the head merged, and a failing or refused PR is stepped over; every pass prints a `train` line per repo and `queued N` for the members it did not attempt (readying a PR stays the operator's; a batch PR, or an archive PR, is one from the repo itself by an allowed author: `pr_authors` in `.fr/triage.yaml`, default the authenticated user, so a fork or foreign-author PR on a batch branch is never merged, only reported once and listed under Needs you now). It closes out each merged batch through its runner after the repo's `post_merge` argument list, merges its archive PR, and dispatches by wave up to `--max-inflight`. In loop mode it also prints one `dedupe` line when it sees a wave go from unfinished to finished while duplicate candidates exist: the count and the `fr triage check` command to judge them (it never judges or writes a duplicate; a wave already finished at start, and `--once`, report nothing). Each wave's sessions open in a herdr workspace of their own, `<prefix>-wave-<n>` (`<prefix>-no-wave` for a batch with no wave; `--workspace-prefix`, default `drive`); once a batch is finished (its archive PR merged) its batch and close-out sessions are closed, never one still working or blocked (it is retried next pass), and a wave workspace its last session empties closes with it; `--keep-sessions` leaves them open, and closing never changes an exit code. `--once` exits 0 acted or done, 3 waiting (blocked batches included: they need the operator), 2 refused; in loop mode a failed or timed-out forge read (each `gh` call is bounded) skips the pass, is reported once, and is read again after `--interval`; `--checkout REPO=PATH` names each clone; a second driver on the state directory is refused. A batch closed out by hand is recorded once as a `closeout` event and never closed out again: either its run is archived, or a PR from the repo itself by an allowed author is open or merged on `chore/closeout-<batch branch>`; an open one is then merged like any other archive PR. **Conflict hand-back:** a real merge conflict is handed back, idle only: an idle batch session is sent the brief; with no live session a fresh one starts on the batch's existing branch through the batch's runner; a working, blocked or unknown session is sent nothing and nothing is recorded, so a later pass retries. The brief says to enter the batch's workspace (`fr isolation up --branch <branch>`), merge `origin/main` without rebasing or force-pushing, resolve the named paths, regenerate generated mirrors (the repo's `mirrors:` in `.fr/triage.yaml`) instead of hand-resolving them, run the suite and push. A `conflict` event per hand-back means a restarted driver never hands the same head back twice, and a batch sharing a refused path with an earlier conflicted one waits behind it. At most two hand-backs per dispatch: the next conflict, at a new head, is held and the batch shows under Needs you now as a merge conflict until its PR merges or it is dispatched or cancelled again. **Export** (`export:` set, single-repo scope only; a group or org scope warns): one PR on `chore/triage-state-wave-<N>` covers every finished wave not yet exported. The driver merges only the commit it pushed, based on the default branch and touching only `<path>/<scope>/`; an open PR on such a branch is reused with the driver's own commit, a merge or close made by hand is reconciled, fork PRs are ignored, and durable files the repo ignores are reported, never force-added. A merge the driver stops on (a conflict or refusal, not a moved head) is recorded in `merge-stops.json` in the state directory at the head it stopped at, so the board shows that card as needing you, and a batch planned behind it as waiting on it, until the head moves or the batch merges.

**The board:** `fr triage board` writes `board.html` beside `triage.html`: a live Kanban of the batches in six lifecycle columns, each card showing its session status and a copyable jump command (`--refresh N` reloads the page every N seconds, default 30; `--open` opens it). Every `--yes` pass of `drive` re-renders it, so while a driver runs it stays fresh on its own; with no driver, `fr triage board --watch [--interval N]` re-collects and re-renders until interrupted (refused while a live drive holds the lock). `fr triage batch focus <id> [--closeout]` switches the terminal to a batch's live session through the runner that dispatched it. Once `board.html` exists, `fr triage render` links it from the Batches section.

## The shape of a judgement

1. **Tier by what the failure costs**: lost work, then a failure that looks like success, then friction. Never by age, label, reporter or how loud the issue is.
2. **Verify against current main, at scale too.** Before `verified: true`, re-read the cited `file:line` at current main — snippets go stale, and at forty issues a fixed bug stays ranked as live. If you did not re-read it, write `verified: false`.
3. **Record line drift** in `detail` (`was :1013, now :1312`); a bug already fixed on main is a close recommendation, not a ranking.
4. **Hunt duplicates and batches.** Same predicate, same file, same sentence: record a duplicate in the
   structured `duplicate_of` field (or `distinct_from` for a pair that only looks alike), never as prose in
   `note`, and name the batch when issues share a subsystem. A shared root cause across three or more issues becomes a
   `patterns` entry.
5. **Forge actions are unrun commands.** A close, a dedupe (on GitHub, `gh issue close N --duplicate-of <url>`, which `check`
   prints for every judged duplicate) or a relabel is the exact forge CLI command (on GitHub, `gh …`) in
   `note` or your report, for the operator to run. Never act on the forge unasked. `batch dispatch|merge|cancel|drive` act only
   with `--yes` (without it they print the plan; `drive` with no ids plans the batches with a wave, else all); pass
   `--yes` only when the operator asked for that action in this session.

## Privacy

State is outside every repo. Keep facts, judgements and board local when the scope is not the operator's org (`.claude/rules/third-party-privacy.md`).
