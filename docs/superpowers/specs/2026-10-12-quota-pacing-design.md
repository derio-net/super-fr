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

**Leases outlast a reset.** The host lease is `3 × interval + 60` minutes = 66 minutes by default
(`lease.lease_duration`), and the cloud lease 75 minutes. A GraphQL or REST reset is never more
than 60 minutes away, so a driver that sleeps until the reset never loses its lease.

**Visibility.** The state repo's visibility is read live before every push (driver-resilience
R11, cloud-triage R8) through `RealGhClient.repo_visibility` → `gh repo view --json visibility`,
a GraphQL call. #1136 suggested caching it; the operator kept the live read and made it
conditional instead (R12).

## Requirements

R1. A new module reads the host's rate budget with `GET /rate_limit` and decides pacing from it. The budget a pass is paced on is the lowest remaining fraction among the resources the configured adapter spends: `graphql` and `core` under `forge.api: graphql`, `core` under `forge.api: rest`. The reset time is that resource's reset.
R2. When a pass meets a rate-limit response, the drive reads `/rate_limit` once to learn the reset, then makes no forge call that spends the exhausted resource until that reset (plus a 30 s margin). A rate-limit response is a `ForgeReadError` whose text the forge's error classifier (`hostclient`'s `rate_limit` kind: 403 or 429 with "rate limit") calls a rate limit, or a pass whose `facts.skipped` or `facts.unviewed` reasons classify that way.
R3. At the start of each pass the drive reads `/rate_limit`. If the paced resource has nothing left, the pass does not run, and the drive waits for the reset as in R2.
R4. A rate-limit response while `/rate_limit` still shows budget left (a secondary limit) backs off starting at `--interval`, doubling with each consecutive such response, capped at 15 minutes. It resets after a pass that meets no rate limit.
R5. When `/rate_limit` cannot be read, pacing fails open: the pass runs as it does today, and the failure is reported once per distinct cause.
R6. The budget floor is a host setting: `quota_floor:` in `~/.config/fr/forge.yaml` beside `api:`, a fraction in (0, 1), default 0.20, overridden by `--quota-floor` on `fr triage batch drive`, `fr triage drive pass` and `fr triage kanban --watch`. A value fr cannot use is refused, naming where it came from, as `forge.api` is.
R7. When the paced budget is below the floor, a pass is essential-only. It collects only the repos with a live batch (a batch whose stage is in `LIVE_STAGES`) and carries every other repo's facts from the last `facts.json` (R10). It dispatches no new batch: each such batch is reported held with reason `quota below floor`. Merges and close-outs run as in a normal pass. The board is not re-rendered, and the loop's next pass waits four times `--interval`.
R8. Before collecting, a pass sends conditional REST probes with the ETags stored from the last successful collect: per scope repo, `repos/{r}/issues?state=all&sort=updated&direction=desc&per_page=1`; per open PR of a live batch, `repos/{r}/commits/{head}/check-runs?per_page=100` and `repos/{r}/commits/{head}/status`. A repo is changed when any of its probes answers other than 304, or has no stored ETag.
R9. A pass in which no repo changed (a quiet pass) skips the collect, the plan and the board. It still renews the lease. It costs no GraphQL points, and only REST requests answered 304.
R10. A pass collects only the changed repos (R8), intersected with the live-batch repos when it is essential-only (R7). Every other repo's issues, PRs, batch PRs, config and visibility are carried unchanged from the last `facts.json`. A carried repo is not unread: its batches are planned as usual, except that an essential-only pass dispatches nothing.
R11. A full pass, reading every scope repo with no probe, runs at least every 15 minutes, and on each process's first pass. A repo's ETags are stored only after a collect that read that repo successfully, and are written together with the `facts.json` they describe, so a failed or partial collect never makes a later probe answer 304 over stale facts.
R12. The state repo's visibility stays a live read before every push (driver-resilience R11 stands). Under both adapters it is read with REST `GET /repos/{r}` sent conditionally with the ETag of the client's last answer; a 304 returns that answer's visibility.
R13. Whenever the drive throttles itself (R2, R3, R4, R7), it logs one line naming the resource, remaining/limit, the reset in UTC, and what it is doing, for example `quota: graphql 812/5000 (16%), resets 16:43Z; below floor 20%: essential-only pass, dispatch held, next pass in 8m`. A quiet pass logs `quiet: N probes unchanged`.
R14. `board.html`'s footer shows the last budget the drive read (resource, remaining/limit, reset) and when `facts.json` was last collected. The board is re-rendered only after a pass that collected something; quiet and essential-only passes keep the last board.
R15. The host drive loop sleeps through a wait. The cloud `fr triage drive pass` (one process per wake) exits 3 with the R13 line, before it takes the lease, when the budget is exhausted or still inside a recorded reset wait. `fr triage kanban --watch` waits for the reset and applies the floor's stretched interval, but holds nothing (it dispatches nothing).
R16. A GitHub App installation token per org (#1136 item 4) is not implemented; it is filed as super-fr#1152.

## Design

### A. The pacing module (R1–R6, R13)

`fr/triage/quota.py` holds the pure pieces, and the IO stays in the adapter:

- `Budget(resource, remaining, limit, reset)` and `read_budget(forge) -> Budget | None`. The
  `Forge` protocol (`collect.py:68`) gains `rate_limit() -> dict`, which both adapters implement
  as `gh api rate_limit` (REST under either API, free). `None` means unreadable (R5).
- `paced(resources, api) -> Budget`: the lowest fraction among the adapter's resources (R1).
- `decide(budget, floor, now, wait) -> Pace`, which is pure: `run`, `essential`, or
  `wait(until, why)`. `wait` carries the R4 backoff state (consecutive secondary hits).
- `quota_line(budget, floor, verdict) -> str`, the one R13 line.
- `quota_floor()`, resolved like `forgeapi.resolve` (`--quota-floor` > host file > 0.20) in
  `fr/forgeapi.py`, beside `api:`, so the host file keeps one reader.

The host loop (`_host_loop`) asks `decide` before `one_pass` and after a `ForgeReadError` or a
rate-limited `facts.skipped`/`unviewed` (R2). A `wait` sleeps until `until`, and nothing in the
loop calls the forge meanwhile. The lease is safe because a reset is at most 60 minutes away and
the host lease is 66 minutes.

### B. Probes and partial collect (R8–R11)

`fr/triage/probe.py` keeps the probe set and the ETag store. `probes.json` sits beside
`facts.json` in the state dir and holds `{probe path: etag}` per repo plus `full_at`, the time of
the last full pass. The `Forge` protocol gains `probe(path, etag) -> (changed: bool, etag)`,
implemented through `gh api -i -H 'If-None-Match: <etag>' <path>`: a `304` first line (with
`gh`'s exit 1) is unchanged, a `200` is changed and yields the new ETag, and any other answer
counts as changed, so a failing probe never hides a change.

`collect_facts_counted` gains `only: set[str] | None` and `previous: Facts | None`. Repos outside
`only` are not read. Their issues, PRs (open and listed), batch PRs, config and visibility are
copied from `previous`, and judged keys in them are resolved from `previous` too. The ETags of a
read repo come back with the facts, and `collect_into` writes `probes.json` only after it has
written `facts.json` (R11). A repo whose read failed keeps its old ETags removed, so the next pass
reads it again.

`run_pass` picks the pass kind: a **full** pass on the first pass of the process or when `full_at`
is 15 minutes old, otherwise probes; then **quiet** (nothing changed), **partial** (`only` =
changed), or **essential** (`only` = changed ∩ live-batch repos, R7).

### C. Essential-only pass (R7)

`drive_pass` (`fr/triage/batch_drive.py`) is pure and takes a `Snapshot`. The snapshot gains
`dispatch_held: str | None`. When it is set, every `dispatch` action the plan would emit becomes
a held action with that reason, and the summary counts it as held. Merges and close-outs are
unchanged. `_write_board` is skipped, and the loop sleeps `4 × interval`.

### D. Conditional visibility (R12)

`RealGhClient.repo_visibility` moves from `gh repo view --json visibility` to `gh api -i
repos/{r}` with the client's last ETag for that repo, kept in memory per client instance.
`RealGhRestClient.repo_visibility` does the same. The answer is still live. `live_visibility`
and `guard_state` are unchanged.

### E. Cloud pass and kanban watch (R15)

`drive_pass_command` (`triage_drive_cmd.py:433`) reads the budget before it takes the lease. If
the budget is exhausted, or the state dir's `probes.json` records a `wait_until` still in the
future, it prints the R13 line and exits 3. The cloud lease (75 minutes) outlasts any reset. Its
probes and partial collect are §B unchanged: `probes.json` travels in the state dir with
`facts.json`. `kanban_watch` calls the same `decide` and sleeps through `wait`. When it is below
the floor it stretches its interval and still renders.

### F. Board footer (R14)

`kanban_render` (`fr/triage/kanban_render.py:389`) reads no clock. The budget and the facts'
`collected_at` are passed in from `write_board`, which takes the last `Budget` the driver read
(the driver passes it; the watch loop reads its own).

## Verification

strategy: none
- quota-reset-wait: none — a real rate limit cannot be produced on demand; a fake forge returning a rate-limit error and a fake `/rate_limit` is the proof.
- quota-floor-essential-pass: none — a fake `/rate_limit` below the floor drives the essential-only pass in unit tests.
- quota-quiet-pass: none — a fake forge answering 304 probes proves no collect and no GraphQL read; the 304 shape is the live capture in Background.
- visibility-conditional-read: none — a fake `gh` run returning the captured 304 shape is the proof.
- quota-board-footer: none — the render is pure; unit tests assert the footer text.
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
