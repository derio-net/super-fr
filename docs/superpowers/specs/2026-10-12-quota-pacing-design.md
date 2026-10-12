# Drive quota pacing — wait for the reset, budget floor, cheap quiet passes

Batch `quota-pacing`: super-fr#1136. Companion to driver-resilience (#1134, shipped in #1137),
which stops a looping driver from *dying* when the shared GraphQL quota runs out; this stops the
drivers from *running it out*.

## Background

One personal token's budget is shared by everything on a host: several org wave drivers, the
coordinator session, and every batch session the drivers dispatch (about 14 on 2026-10-10). The
GraphQL budget (5,000 points/hour) ran out on 2026-10-10 and again on 2026-10-11 at 16:20 UTC.
While it is out, every batch session's `gh` calls fail too, so work stalls everywhere.

**What a pass costs.** Every drive pass starts with `recollect` → `triage_cmd.collect_into` →
`collect.collect_facts_counted` (`fr/triage/collect.py:486`), which reads every repo of the scope
in full on every pass: `gh issue list` (1,000 open issues), `gh pr list --state all` (200),
`gh pr list` of open PRs with `files,statusCheckRollup,mergeable,…`, the repo's
`.fr/triage.yaml`, one comment read per `fr:in-progress` issue, and one `view_issue` per judged
key that is no longer open (`collect.py:539`). Measured on 2026-10-12, one cold
`fr triage collect --repo derio-net/super-fr` cost **7 GraphQL points**. An org scope repeats
that per repo, every `--interval` (default 120 s, `triage_batch_cmd.DEFAULT_INTERVAL`), whether
or not anything changed: 30 passes an hour × N repos × ~7 points runs one org driver alone into
thousands of points an hour.

**What a rate-limited pass does today.** A failing forge read raises `ForgeReadError`; the host
loop (`_host_loop`, `triage_batch_cmd.py`) prints `pass skipped, retrying every {interval}s` once
per cause and retries every interval. Each retry spends requests that cannot succeed before the
reset GitHub already announced. `fr triage kanban --watch` (`triage_kanban_cmd.py:425`) does the
same. Two rate-limit outcomes do not raise at all: in org scope a repo whose reads fail is
recorded under `facts.skipped`, and a judged key whose view fails under `facts.unviewed`
(`collect.py:624`). So a pass can "succeed" while the quota is exhausted.

**Free reads exist.** `GET /rate_limit` does not count against any budget. A conditional REST
request (`If-None-Match: <etag>`) answered `304 Not Modified` does not count either. Captured
live 2026-10-12 through `gh api -i -H 'If-None-Match: W/"…"' 'repos/derio-net/super-fr/issues?per_page=1&state=all'`:
the first line of output is `HTTP/2.0 304 Not Modified`, `gh` exits 1, and the core budget's
`used` did not move.

**Leases and waits.** The host lease is `3 × interval + 60` minutes (`lease.lease_duration`,
taken at the start of each pass by `one_pass`): 66 minutes at the default interval, but
`--interval` allows 1 second, and the lease's clock starts before a pass that can take minutes.
A wait of up to 60 minutes plus a margin is therefore not safe by arithmetic alone, so R16 renews
the lease during a long wait instead of relying on a timing argument.

**How exhaustion is reported.** `gh.classify` (`gh.py:672`), which the forge's error kind
delegates to (`hostclient.py:52`), calls an error a rate limit only when its text has `403` and
`rate limit`. An exhausted GraphQL budget comes back as `GraphQL: API rate limit exceeded for
user ID …` (HTTP 200 with a `RATE_LIMITED` error), with no status code, so today it classifies as
`unknown`. And by the time the loop sees it, the error is plain text (`ForgeReadError`'s message,
a `Skipped`/`Unviewed` reason). R2 therefore defines its own text rule.

**Visibility.** The state repo's visibility is read live before every push (driver-resilience
R11, cloud-triage R8) through `RealGhClient.repo_visibility` → `gh repo view --json visibility`,
a GraphQL call. #1136 suggested caching it; the operator kept the live read and made it
conditional instead (R12).

## Requirements

R1. A new module reads the host's rate budget with `GET /rate_limit` and decides pacing from it. The budget a pass is paced on is the lowest remaining fraction among the resources the configured adapter spends: `graphql` and `core` under `forge.api: graphql`, `core` under `forge.api: rest`. The reset time is that resource's reset.
R2. A rate-limit response is recognised from text: a `ForgeReadError` message, or a `facts.skipped` / `facts.unviewed` reason, that contains `rate limit` (any case, which covers REST 403/429 `API rate limit exceeded`, `secondary rate limit`, and GraphQL's `API rate limit exceeded for user ID …`, which carries no status code) or `RATE_LIMITED`. A pass that meets one ends before its snapshot reads and acts on nothing. It reads `/rate_limit` once to learn the reset, and then the drive makes no forge call that spends the exhausted resource until that reset plus 30 s (R16 is the one exception).
R3. At the start of each pass the drive reads `/rate_limit`. If the paced resource has nothing left, the pass does not run, and the drive waits as in R2.
R4. A rate-limit response while `/rate_limit` still shows budget left (a secondary limit) backs off starting at `--interval`, doubling with each consecutive such response, capped at 15 minutes. The count resets after a pass that meets no rate limit.
R5. When `/rate_limit` cannot be read, pacing fails open: the pass runs as it does today, and the failure is reported once per distinct cause.
R6. The budget floor is a host setting: `quota_floor:` in `~/.config/fr/forge.yaml` beside `api:`, a fraction in (0, 1), default 0.20, overridden by `--quota-floor` on `fr triage batch drive`, `fr triage drive pass` and `fr triage kanban --watch`. A value fr cannot use is refused, naming where it came from (the flag or the file), as `forge.api` is.
R7. When the paced budget is below the floor, a pass is essential-only. It reads only live-batch repos: the repos of batches whose stage is in `LIVE_STAGES` (`batch_dispatch.py:38`: `dispatched`, `pr-open`) or that have an open close-out or archive PR. Of those it collects the changed ones (R10), or all of them on a forced full pass (R11). It dispatches no new batch. Each such batch is reported held with reason `quota below floor` and counted as pending, never as `Summary.held`, so a below-floor pass never ends the drive as stalled. Merges and close-outs run as in a normal pass. The board is not re-rendered, and the next pass waits four times `--interval`.
R8. Probes are conditional REST requests sent with stored ETags. Per scope repo: `repos/{r}/issues?state=all&sort=updated&direction=desc&per_page=1`. Per open PR of a live batch, and per open close-out or archive PR: `repos/{r}/commits/{head}/check-runs?per_page=100` and `repos/{r}/commits/{head}/status`. A repo is changed when any of its probes answers other than 304 (a failed probe included), or has no stored ETag. A repo's probes are always sent before its collect, never after.
R9. A pass is quiet when every probe answers 304 and `judgements.yaml` is byte-identical to the one the last planned pass read. A quiet pass skips the collect, the snapshot's reads, the plan and the board. It still renews the lease. It costs no GraphQL point, and only REST requests answered 304 plus at most one visibility read per process (R12).
R10. A pass that is not quiet collects only the changed repos, intersected with the live-batch repos when it is essential-only (R7). Every other repo is carried from the last `facts.json`: its issues, PRs, batch PRs, config and visibility. Each issue's PR links are recomputed from the union of this pass's read PRs and the carried PRs' previous links, so a PR in one repo that closes an issue in another stays linked whichever side was read. A carried repo is never unread (no `unread` report, its batches count toward the in-flight cap and dependencies). The snapshot makes no per-batch live read for a carried repo's batches (`pr_view`, required checks, merge commit, close-out, archive), so those batches are not merged, closed out or archived this pass. They are dispatched as usual, except in an essential-only pass.
R11. A full pass sends every repo's probes unconditionally (no ETag), then collects every repo. It runs on the first pass after `pacing.json` is missing (a new host, a fresh or re-homed cloud session) and whenever its recorded `full_at` is at least 15 minutes old. Below the floor, a full pass is narrowed to the live-batch repos (R7). After a collect, the ETags of exactly the repos it read successfully are stored, written after the `facts.json` they describe. A repo whose read failed has its ETags dropped, so a failed or partial collect never makes a later probe answer 304 over stale facts.
R12. The state repo's visibility stays a live read before every push (driver-resilience R11 stands). Under both adapters it is read with REST `GET /repos/{r}`, sent conditionally with the ETag of this process's last answer for that repo, held at module scope (the visibility client is built fresh per push, `triage_cmd.make_visibility_client`). A 304 returns that answer's visibility.
R13. Whenever the drive throttles itself (R2, R3, R4, R7), it logs one line naming the resource, remaining/limit, the reset in UTC, and what it is doing, for example `quota: graphql 812/5000 (16%), resets 16:43Z; below floor 20%: essential-only pass, dispatch held, next pass in 8m`. A quiet pass logs `quiet: N probes unchanged`.
R14. `board.html`'s footer shows the last budget the drive read (resource, remaining/limit, reset) and when `facts.json` was last collected. The board is re-rendered only after a pass that collected something; quiet and essential-only passes keep the last board.
R15. Pacing state lives in `pacing.json` in the local state dir, beside `facts.json`: the stored ETags per repo and probe path, `full_at`, `wait_until`, the R4 backoff count, `next_pass_at` (R7's stretch), the `judgements.yaml` digest of the last planned pass, and the last budget read. Neither `pacing.json` nor `facts.json` is added to the state ref's `REF_FILES`, so a fresh or re-homed cloud session starts with a full pass. Any loop that meets a rate limit writes `wait_until`.
R16. A wait never lets the drive's lease lapse. The host loop never sleeps past its lease's expiry minus 5 minutes: a wait or stretched interval longer than that wakes, renews the lease (the git push and its R12 visibility read, the one call R2 allows during a wait), and sleeps again. The cloud `fr triage drive pass`, one process per wake, exits 3 with the R13 line when `/rate_limit` shows the paced resource exhausted, when `wait_until` or `next_pass_at` is still in the future, or below the floor until `next_pass_at`. In each case it first renews the lease if the lease would lapse before its next wake.
R17. `fr triage kanban --watch` (`_watch`) uses the same pacing: probes, quiet skip and carry through `collect_into`, sharing `pacing.json` (the watch never runs while a drive holds the lock). It waits for the reset and stretches its interval below the floor. It holds nothing, because it dispatches nothing.
R18. A GitHub App installation token per org (#1136 item 4) is not implemented; it is filed as super-fr#1152.

## Design

### A. The pacing module (R1–R6, R13)

`fr/triage/quota.py` holds the pure pieces, and the IO stays in the adapter:

- `Budget(resource, remaining, limit, reset)` and `read_budget(forge) -> Budget | None`. The
  `Forge` protocol (`collect.py:68`) gains `rate_limit() -> dict`, which both adapters implement
  as `gh api rate_limit` (REST under either API, free). `None` means unreadable (R5).
- `paced(resources, api) -> Budget`: the lowest fraction among the adapter's resources (R1).
- `is_rate_limited(text) -> bool`: R2's text rule. It is separate from `gh.classify`
  (`gh.py:672`), which needs `403` and so misses GraphQL exhaustion. Tests use the real GraphQL
  error text.
- `decide(budget, floor, now, state) -> Pace`, which is pure: `run`, `essential`, or
  `wait(until, why)`. `state` is the loaded `pacing.json` (R15) and carries the R4 backoff count.
- `quota_line(budget, floor, verdict) -> str`, the one R13 line.
- `quota_floor(flag)`, resolved like `forgeapi.resolve` (flag > host file > 0.20) in
  `fr/forgeapi.py`, beside `api:`, so the host file keeps one reader.

The host loop (`_host_loop`) asks `decide` before `one_pass`, after a `ForgeReadError`, and when
`recollect` returns a rate-limited `skipped`/`unviewed` reason (R2: the pass ends there, before
`snapshot`). A `wait` sleeps in chunks bounded by R16, and each chunk boundary only renews the
lease. A test runs a wait longer than the remaining lease and asserts the renewal.

### B. Probes and partial collect (R8–R11, R15)

`fr/triage/probe.py` keeps the probe set and reads and writes `pacing.json` atomically
(`write_text_atomic`). The `Forge` protocol gains `probe(path, etag) -> (changed, etag)`,
implemented through `gh api -i [-H 'If-None-Match: <etag>'] <path>`: a `304` first line (with
`gh`'s exit 1) is unchanged, a `200` is changed and yields the new ETag, and anything else is
changed with no ETag.

Order per pass: load `pacing.json`; send the probes (unconditional on a full pass), keeping each
answer's ETag *pending*; decide quiet / partial / essential / full; collect the chosen repos; write
`facts.json`; then promote the pending ETags of the repos read successfully, drop those of a
failed repo, and write `pacing.json`. Because the probe precedes the collect, a change landing in
between yields a newer ETag next time (a 200), never a stale 304. A test interleaves exactly that.

`collect_facts_counted` gains `only: set[str] | None` and `previous: Facts | None`. Repos outside
`only` are not read. Their issues, unlinked PRs, batch PRs, config and visibility come from
`previous`, and their judged keys are resolved from `previous`. Links: `invert` runs over this
pass's read PRs, then each issue (read or carried) also keeps the previous links whose PR lives in
a carried repo (R10). A test covers a PR in repo A closing an issue in repo B, with A read and B
carried and the other way round.

`snapshot` (`triage_batch_cmd.py:2868`) receives the set of carried repos and skips the
per-batch live reads (`pr_view`, `pr_required_checks`, merge commit, `_hand_closeout`,
`_archive_prs`, claim and export reads, `triage_batch_cmd.py:2901-2979`) for their batches. The
plan's merge, close-out and archive actions for those batches are dropped. `drive_pass` is
unchanged.

What a quiet pass defers, at most until the next changed or full pass (15 minutes), is accepted
latency: time-due decisions (`closeout_due`, `STALE_CLOSEOUT`, claim and dispatch age), release
tags read through the clone, runner session upkeep, and a direct push to a default branch's
`.fr/triage.yaml`. A `judgements.yaml` edit is never deferred (R9).

### C. Essential-only pass (R7)

The `Snapshot` (`batch_drive.py:119`) gains `dispatch_held: str | None`. When it is set,
`drive_pass` turns every `dispatch` action into a held action with that reason, counted in
`Summary.pending`, never `Summary.held`, which `stalled` reads (`batch_drive.py:260`, `_host_loop`
exits 3 on it). A test drives a below-floor pass with only proposed batches and asserts the loop
keeps going. `_write_board` is skipped, and `pacing.json`'s `next_pass_at` is set to
`now + 4 × interval`, which the host loop sleeps toward within R16's bound.

### D. Conditional visibility (R12)

`RealGhClient.repo_visibility` moves from `gh repo view --json visibility` to `gh api -i
repos/{r}`, sent with the ETag of this process's last answer for that host and repo. That ETag is
kept in a module-level map because `make_visibility_client` (`triage_cmd.py:326`) builds a new
client per push. `RealGhRestClient.repo_visibility` shares the same map and request. The answer is
still live. `live_visibility` and `guard_state` are unchanged.

### E. Cloud pass and kanban watch (R16, R17)

`drive_pass_command` (`triage_drive_cmd.py:433`) loads `pacing.json` and reads the budget before
its pass. It exits 3 with the R13 line when the paced resource is exhausted, when `wait_until` or
`next_pass_at` is in the future, or, below the floor, until `next_pass_at`. If the lease would lapse
before the next wake (`now + --interval`), it first renews it. Otherwise its pass is §B's,
including the probes. `pacing.json` is local, so a re-homed session's first pass is full. The
watch loop `_watch` (`triage_kanban_cmd.py:397`) collects through the same `collect_into` path, so
it probes, skips quiet passes and carries. It sleeps through `wait` and, below the floor, through
`4 × interval`, and it renders after any pass that collected.

### F. Board footer (R14)

`kanban_render` (`fr/triage/kanban_render.py:389`) reads no clock. The last budget and the facts'
`collected_at` reach it through `write_board` (`triage_kanban_cmd.py:332`), which reads them
from `pacing.json` and `facts.json`.

## Verification

strategy: none
- quota-reset-wait: none — a real rate limit cannot be produced on demand; a fake forge raising the captured GraphQL and REST rate-limit texts plus a fake `/rate_limit` is the proof (R2, R3).
- quota-secondary-backoff: none — the backoff and its fail-open sibling are pure decisions over a fake `/rate_limit` (R4, R5).
- quota-floor-config: none — floor resolution and refusal are unit-tested over a temp host file and the flag (R6).
- quota-floor-essential-pass: none — a fake `/rate_limit` below the floor drives the essential-only pass, including the never-stalled case (R7).
- quota-quiet-pass: none — a fake forge answering 304 probes proves no collect, no GraphQL read and no plan (R8, R9).
- quota-partial-carry: none — collect with `only`/`previous` over fake forge data, cross-repo links included (R10).
- quota-etag-consistency: none — a change interleaved between probe and collect, and a failed repo dropping its ETags, are unit-tested (R11, R15).
- quota-lease-safe-wait: none — a fake clock and lease prove the wait renews the lease and the cloud pass exits 3 (R16, R17).
- visibility-conditional-read: none — a fake `gh` run returning the captured 304 shape is the proof (R12).
- quota-board-footer: none — the render is pure; unit tests assert the footer and the throttle line (R13, R14).
- quota-shared-token-live: live — only a released build driving real org scopes on one token overnight can show the budget no longer runs out.

## Test Plan

1. **post-merge — operator-driven.** On the released build, run the org drivers overnight on one
   token, as on 2026-10-10. Confirm with `gh api rate_limit` that the GraphQL budget does not
   reach 0, and that the driver logs show `quiet:` passes and, if the floor was crossed, `quota:`
   lines (row `quota-shared-token-live`).

## Non-goals

- A GitHub App installation token per org (#1136 item 4): filed as super-fr#1152, with the
  operator's open questions.
- Pacing batch sessions' own `gh` calls. Only the drive and watch loops are paced; the floor
  leaves room for the sessions.
- Caching visibility: R12 keeps the live read.
- An incremental collect that re-reads single issues by `updated_at`: the per-repo probe and
  carry give the quiet-pass saving without changing what a repo's collect reads.
- Coordinating several drivers through a shared host file: each reads `/rate_limit` itself,
  which is free and always current.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-10-12-quota-pacing | `derio-net/super-fr` | `2026-10-12-quota-pacing` | — |
