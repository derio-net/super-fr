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

Everything lives in the scope's state directory: the workspace's `.fr/triage-state/<scope>/`, or `~/.cache/fr/triage/<scope>/` outside a clone (`<scope>` is `owner--repo` for `--repo OWNER/REPO`, `owner` for `--org OWNER`, lowercased). `--repo A/B,C/D` is a group; two repos with same name are refused (keys are `<repo-name>#<n>`); batches stay single-repo. fr reaches GitHub through one host setting, `forge.api: rest | graphql` (`FR_FORGE_API`, else `api:` in `~/.config/fr/forge.yaml`, default `graphql`); a Claude Code cloud session needs `rest`, since its proxy refuses GraphQL.

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
    off: on GitHub, `gh issue view`) and the code; a first run creates the file with `schema: 8` and `tiers`. Compare against ALL judgements.
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
schema: 8
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
**Schema 8:** 1–7 still load; engine writes upgrade the stamp. Only the engine appends `events:` (`dispatch`, `cancel`, `post_merge`, `closeout`, `conflict`, `claims_released`, `replacement`, `claim_taken`); stage is derived. `batch create|edit --wave N --after ID` sets wave/dependencies (unknown id, self/cycle refused); only `merged` meets a dependency. `batch dispatch` runs `/fr-goal` or `/fr-debugging` (`skill`) on launch model, else orchestrator binding, and marks issues taken; `batch merge` merges in order; `batch cancel` withdraws. Adopt hand-started sessions with `batch adopt --list`, `batch create`, then `adopt ID --tab T --branch B`: no launch, idle agent only; renames branch, supersedes an open PR, labels tab/agent and records dispatch.
**The driver:** `fr triage batch drive` runs the batches named, else those with a wave, else all, to completion: each pass treats a repo's ready PRs as a merge train: only the head of them (wave, then order, then id) is merged (with the forge's default method, else `merge_method: merge | squash | rebase` in `.fr/triage.yaml`, which a repo allowing several methods needs under `rest`) or, when behind its base, updated, the next one follows in the same pass once the head merged, and a failing or refused PR is stepped over; every pass prints a `train` line per repo and `queued N` for the members it did not attempt (readying a PR stays the operator's; a batch PR, or an archive PR, is one from the repo itself by an allowed author: `pr_authors` in `.fr/triage.yaml`, default the authenticated user, so a fork or foreign-author PR on a batch branch is never merged, only reported once and listed under Needs you now). It closes out each merged batch through its runner after the repo's `post_merge` argument list (the host driver's: the cloud driver runs no `post_merge`, since every session it starts installs the current release), merges its archive PR, and dispatches by wave up to `--max-inflight`. In loop mode it also prints one `dedupe` line when it sees a wave go from unfinished to finished while duplicate candidates exist: the count and the `fr triage check` command to judge them (it never judges or writes a duplicate; a wave already finished at start, and `--once`, report nothing). Each wave's sessions open in a herdr workspace of their own, `<prefix>-wave-<n>` (`<prefix>-no-wave` for a batch with no wave; `--workspace-prefix`, default `drive`); once a batch is finished (its archive PR merged) its batch and close-out sessions are closed, never one still working or blocked (it is retried next pass), and a wave workspace its last session empties closes with it; `--keep-sessions` leaves them open, and closing never changes an exit code. `--once` exits 0 acted or done, 3 waiting (blocked batches included: they need the operator), 2 refused; in loop mode a failed or timed-out forge read (each `gh` call is bounded) skips the pass, is reported once, and is read again after `--interval`; `--checkout REPO=PATH` names each clone; a second driver on the state directory is refused. A batch closed out by hand is recorded once as a `closeout` event and never closed out again: either its run is archived, or a PR from the repo itself by an allowed author is open or merged on `chore/closeout-<batch branch>`; an open one is then merged like any other archive PR. **Conflict hand-back:** a real merge conflict is handed back, idle only: an idle batch session is sent the brief; with no live session a fresh one starts on the batch's existing branch through the batch's runner; a working, blocked or unknown session is sent nothing and nothing is recorded, so a later pass retries. The brief says to enter the batch's workspace (`fr isolation up --branch <branch>`), merge `origin/main` without rebasing or force-pushing, resolve the named paths, regenerate generated mirrors (the repo's `mirrors:` in `.fr/triage.yaml`) instead of hand-resolving them, run the suite and push. A `conflict` event per hand-back means a restarted driver never hands the same head back twice, and a batch sharing a refused path with an earlier conflicted one waits behind it. At most two hand-backs per dispatch: the next conflict, at a new head, is held and the batch shows under Needs you now as a merge conflict until its PR merges or it is dispatched or cancelled again. **Export** (`export:` set, single-repo scope only; a group or org scope warns): one PR on `chore/triage-state-wave-<N>` covers every finished wave not yet exported. The driver merges only the commit it pushed, based on the default branch and touching only `<path>/<scope>/`; an open PR on such a branch is reused with the driver's own commit, a merge or close made by hand is reconciled, fork PRs are ignored, and durable files the repo ignores are reported, never force-added. A merge the driver stops on (a conflict or refusal, not a moved head) is recorded in `merge-stops.json` in the state directory at the head it stopped at, so the board shows that card as needing you, and a batch planned behind it as waiting on it, until the head moves or the batch merges.
**Claims:** several scopes (one per repo, org or group, on one host or many) can work the same issues, so a scope claims each issue it plans to act on: an `fr:claimed` label and one hidden marker comment naming the claiming scope (its scope id, `fr triage scope show`, derived from a random per-host id; a pod or container sets `FR_HOST_ID` so its id survives a restart). A claim is owed for every member of a batch with a wave from the moment the wave is set, and for a wave-less batch from its dispatch; `batch create|edit --yes`, `fr triage claim sync --yes` and every `drive --yes` pass write the owed claims and refresh the heartbeat, and a cancelled, abandoned or finished batch releases them. Another scope's claim is hands-off: judge the issue as usual, but never batch, dispatch, merge, close out or archive it; the commands refuse it and the driver reports the batch as held by another scope, apart from the batches that need the operator. A claim expires after 24 hours unless refreshed (`claim_expiry_hours`), yet an expired claim still holds its issue: it is reported (`fr triage check`, `fr triage claim list`: held elsewhere, expired claims, claims owed) and never taken automatically. Taking one over and releasing another scope's are the operator's: never run them on your own judgement. To take one over, put the issue in a batch of this scope (`batch create|edit` admit a member whose foreign claim is expired or stale, never a fresh one), then `fr triage claim take <key> --batch <id> --yes`; the take makes that member owed, wave or not. `fr triage claim release <key> --yes` releases another scope's expired claim. A claim is stale once its heartbeat is older than a quarter of its expiry window: `--stale` on `take` or `release` acts on it before it expires, and `fr triage scope retire <scope-id> --yes` releases every claim of a scope that stopped, refused while any of them is fresh unless `--force`. Only markers by the repo's own trusted authors count. The scope's own settings live on the host, never in the repo, in `<state dir>/scope.yaml`: `claim_expiry_hours`, `board_name` and `publish`, an argument list (never a shell string) with `{board}`, `{name}` and `{scope_id}` placeholders that fr runs after every `drive --yes` pass that rendered the board and for each render of `fr triage board --publish` (each `--watch` iteration included), with a 120 second timeout, no shell, the operator's environment and the scope's state directory as its working directory; a failure warns once per cause and never changes an exit code. The default board name is `<repo> batches`, `<owner> batches` or `<scope name> batches`. The board lists what other scopes hold under "Held elsewhere", expired claims marked, and each batch card shows when its claims expire.

**The board:** `fr triage board` writes `board.html` beside `triage.html`: a live Kanban of the batches in six lifecycle columns, each card showing its session status and a copyable jump command (`--refresh N` reloads the page every N seconds, default 30; `--open` opens it). Every `--yes` pass of `drive` re-renders it, so while a driver runs it stays fresh on its own; with no driver, `fr triage board --watch [--interval N]` re-collects and re-renders until interrupted (refused while a live drive holds the lock). `fr triage batch focus <id> [--closeout]` switches the terminal to a batch's live session through the runner that dispatched it. Once `board.html` exists, `fr triage render` links it from the Batches section. **Runner constraints and session upkeep:** The herdr runner works only from inside a herdr pane: outside one (`HERDR_ENV` unset) it refuses, so run `fr triage batch drive` and `dispatch` from a herdr pane; herdr is never driven from outside it. Two settings in the repo's `.fr/triage.yaml` keep the sessions the driver leaves behind healthy. `post_merge_restart: idle` (default `none`) restarts every idle Claude Code session once per pass that ran the repo's `post_merge`, after the close-outs it started, so they pick up what that step installed; `fr-herdr restart-idle` does the same by hand (a dry run until `--yes`; it never touches a pane that is working, holds a draft, or is the driver's own). `idle_session_minutes` (default 60) is how old a batch session's dispatch (a close-out's start) must be, while the runner reports it idle or done with no PR (a close-out: no archive PR; a cancelled batch is never reported), before the driver reports it once with a paste-ready `fr triage batch focus` command and the board marks its card as needing you; reporting never ends the drive. **The cloud driver** (a long-lived Claude Code cloud session; setup, prerequisites and the `agents` artifact its workers need: `docs/cloud-setup.md`, checked by `fr cloud doctor`): its brief carries a host id and the scope's state repo. Every wake: (1) write that id to `~/.config/fr/host-id` and `api: rest` to `~/.config/fr/forge.yaml` when either is missing (a restarted container keeps the same scope id and lease); (2) list your sessions' statuses and blocked notes as JSON; (3) `fr triage drive pass --repo R --statuses <json> --outbox <outbox> [--state-repo S] [--generation N]` (it restores the state, renews the lease, updates fr, collects and does every forge action itself; exit 3 is nothing to do but wait); (4) execute each outbox request exactly as its `execute` says (create, message, re-home or archive a session; a tag lookup first, so a replay never creates twice); (5) `fr triage drive record --outbox <outbox> --result <results>`; (6) schedule the next wake (every `--interval` minutes, beside PR-activity subscriptions and an hourly Routine). Policy is fr's, never yours: never merge, dispatch or label by hand. Every batch goes through the `claude-cloud` runner, whatever `launch.runner` says.

**Managed upkeep/replacement:** herdr accepts Claude and `opencode` with explicit provider/model; controls live in the primary checkout, branch work in isolation. Managed OpenCode restarts fresh from durable state; delivered drafts HOLD, current handbacks precede HOLD, close-out retains pickup gates; Claude resumes. `batch replace ID --harness H --model M --reason WHY` previews (omit harness for model-only); `--yes` acts only when requested, harness changes require explicit model. Scope then pane locks preserve original dispatch/time/branch/PR/reservation/pane/name. Schema-7 audit events never change lifecycle (read 1–7). Pending/draft/dialog/busy/self/unknown observations refuse input; never answer dialogs or replay uncertain briefs. `--repair --reason WHY --yes` reconciles both stores without relaunch/resubmission; target model alone is not uptake proof. Recovery/client-live walk: `docs/herdr-control-sessions.md`; operator evidence is owed before Ready.
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
   `note` or your report, for the operator to run. Never act on the forge unasked. `batch dispatch|adopt|merge|cancel|drive` act only
   with `--yes` (without it they print the plan; `drive` with no ids plans the batches with a wave, else all); pass
   `--yes` only when the operator asked for that action in this session.

## Privacy

A scope's state lives in its workspace, out of git, and its durable copy is the branch `refs/heads/fr-triage/<scope-id>` (an orphan holding only the state; a branch because the cloud git proxy writes nothing outside `refs/heads/`), which fr fetches before reading and pushes after every change (`fr triage state fetch|push` by hand). A scope whose state is still on the legacy `refs/fr/triage/<scope-id>` is restored from it, and the next push creates the branch. A push the remote refuses (not another writer) is a warning: the state stays local until a push succeeds. A single-repo scope keeps the ref in that repo; a group or org scope keeps it in a `state_repo` the operator chooses once, on the first collect: one of its private repos when any is private, else a new repo just for the refs or one of its public repos (then a private repo's issue added later would leak). The privacy guard refuses, naming the issue and the state repo, to judge, batch or wave a private repo's issue into a scope whose state repo is public, and checks again before every push and export. Keep facts, judgements and board local when the scope is not the operator's org (`.claude/rules/third-party-privacy.md`).
