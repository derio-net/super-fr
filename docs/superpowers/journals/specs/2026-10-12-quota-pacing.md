# Journal: 2026-10-12-quota-pacing

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-12T06:11:02+00:00 input=true -->
### operator-brief · discovery · Operator brief — batch quota-pacing, super-fr#1136

/fr-goal drive: pace forge reads against the shared GraphQL quota (wait for reset, budget floor, cheap quiet passes)

Batch `quota-pacing` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#1136: drive: pace forge reads against the shared GraphQL quota (wait for reset, budget floor, cheap quiet passes)
Observed in this scope: on a rate-limited pass the driver logs `pass skipped, retrying every 120s` and retries blind until GitHub's reset; the shared GraphQL budget ran out on 2026-10-10 and again on 2026-10-11 (16:20 UTC) while three org drivers and ~14 batch sessions shared one token. Companion to #1134 (survive) — this one stops the exhaustion.
Note: Item 4 (a GitHub App installation token per org, separate budgets) is an operator design decision: brainstorm it or file it as a follow-up, do NOT implement it unasked. Items 1-3 (wait for the reset, budget floor, cheap quiet passes) are in scope; item 5 optional. The PR stays a draft until the operator readies it.

## Why these belong together
Companion to super-fr#1134 in driver-resilience (survive exhaustion); this stops the exhaustion. Runs after driver-resilience merges because both change the drive loop's forge-read handling. Item 4 (GitHub App token per org) is an operator design decision: brainstorm or file as a follow-up, never implement unasked. The PR stays a draft until the operator readies it.

## Delivery rules
- Work on branch `feat/batch-quota-pacing`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1136
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

Issue #1136 body (asks): 1. wait for the reset instead of retrying blind (X-RateLimit-Reset / resetAt); 2. pace against the budget — read GET /rate_limit at pass start, below a floor (e.g. 20%) stretch the interval and drop non-essential reads (collect, board re-renders), keep merge and close-out reads; 3. make a quiet pass nearly free — conditional REST (ETag, 304 free), or query only what changed since the last pass, cache the state repo's visibility for the run; 4. (operator design decision) GitHub App installation token per org; 5. (optional) report quota in the board footer or driver log. Acceptance: with N drivers on one token, a driver never makes a forge call between a rate-limit response and the reset it carried; a pass with no forge changes costs a small fixed number of points independent of claimed issues; the driver log shows the remaining quota whenever it throttles itself.

<!-- fr:journal kind=decision scope=spec id=q-floor-host created=2026-10-12T06:11:02+00:00 -->
### q-floor-host · decision · Budget floor is a host setting, default 20%

Operator chose `quota_floor:` in ~/.config/fr/forge.yaml beside `api:` (default 0.20), overridable by `--quota-floor` on the drive. The token is per host. (R6)

<!-- fr:journal kind=decision scope=spec id=q-below-floor-essential created=2026-10-12T06:11:02+00:00 -->
### q-below-floor-essential · decision · Below the floor, an essential-only pass

Operator chose to collect only live-batch repos, skip the board render and publish, and stretch the interval 4x; merges and close-outs keep moving. (R7)

<!-- fr:journal kind=decision scope=spec id=q-quiet-etag-probe created=2026-10-12T06:11:02+00:00 -->
### q-quiet-etag-probe · decision · Quiet passes are gated by ETag probes

Operator chose conditional REST probes (per-repo issues sorted by updated, per live batch PR head check-runs/status). All 304 skips collect and render. A full pass is forced at least every 15 minutes. (R8, R9, R11)

<!-- fr:journal kind=decision scope=spec id=q-visibility-conditional created=2026-10-12T06:11:02+00:00 -->
### q-visibility-conditional · decision · Visibility stays live, read conditionally

Operator chose to keep driver-resilience R11's live read, moved to REST GET /repos/{r} with an ETag (a 304 is still the server's live answer), over caching it for the run. (R12)

<!-- fr:journal kind=decision scope=spec id=q-loops-all created=2026-10-12T06:11:02+00:00 -->
### q-loops-all · decision · Pacing applies to the drive loop, the cloud pass and the kanban watch

Operator chose one shared pacing module for all three. The cloud pass skips and exits 3 when exhausted; the kanban watch waits for the reset. (R15)

<!-- fr:journal kind=decision scope=spec id=q-app-token-followup created=2026-10-12T06:11:02+00:00 -->
### q-app-token-followup · decision · Item 4 filed as a follow-up issue, not implemented

Operator chose to file a follow-up issue with a sketch. Filed as super-fr#1152. (R16)

<!-- fr:journal kind=decision scope=spec id=q-report-log-footer created=2026-10-12T06:11:02+00:00 -->
### q-report-log-footer · decision · Quota reported in the throttle log line and the board footer

Operator chose a log line on every throttle plus the last-read budget in board.html's footer. (R13, R14)

<!-- fr:journal kind=decision scope=spec id=q-verify-none-plus-live created=2026-10-12T06:11:02+00:00 -->
### q-verify-none-plus-live · decision · Verification strategy none, plus one post-merge live row

Operator chose strategy none (unit tests with fake /rate_limit and 304 answers) and one post-merge live Test Plan row (overnight org drivers on one token). (Verification section, quota-shared-token-live)

<!-- fr:journal kind=decision scope=spec id=q-board-render-on-change created=2026-10-12T06:11:02+00:00 -->
### q-board-render-on-change · decision · Board re-rendered only after a pass that collected

Operator chose to keep the last board on quiet and essential-only passes; the footer shows when facts were last collected. (R14)

<!-- fr:journal kind=decision scope=spec id=q2-hold-dispatch created=2026-10-12T06:11:02+00:00 -->
### q2-hold-dispatch · decision · No dispatch below the floor

Round 2, from the essential-only answer and snapshot() at triage_batch_cmd.py:2876. Operator chose to hold all new dispatches below the floor (reported held, reason `quota below floor`), because each new batch session spends quota from the same token; merges and close-outs continue. (R7)

<!-- fr:journal kind=decision scope=spec id=q2-partial-collect created=2026-10-12T06:11:02+00:00 -->
### q2-partial-collect · decision · Collect only the repos whose probes changed

Round 2, from the ETag-probe answer and collect's per-repo reads (collect.py:539). Operator chose to collect only changed repos and carry the others' facts from the last facts.json; the same splice serves the essential-only pass. (R10)

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-10-12T06:11:17+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: design-risk. Round 1 chose an essential-only pass and an ETag probe gate. Checking those answers against the code showed that snapshot() (triage_batch_cmd.py:2876) treats a repo missing from a pass's collect as unread, so its batches sit the pass out. That left two decisions round 1 could not settle: whether to dispatch below the floor, and whether a partial change collects only the changed repos (collect.py:539 reads per repo).

<!-- fr:journal kind=review scope=spec id=sr-review created=2026-10-12T06:19:35+00:00 -->
### sr-review · review · spec review of 2026-10-12-quota-pacing

13 findings, all in scope: sr-1 to sr-13. All 11 journal decisions honoured. Codebase anchors verified (see finding bodies).

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-10-12T06:19:35+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · Quota-held dispatches counted as Summary.held would end the host drive as stalled

§C counted held-below-floor dispatches as held; Summary.stalled (batch_drive.py:260) reads held and _host_loop exits 3 on it. Fix: count them as pending, test the proposed-only below-floor case.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-10-12T06:19:35+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · Cloud pass: every drive pass is a first pass; facts.json and probes.json are not on the state ref

REF_FILES (state_ref.py:53) carries neither file. Fix: state they are local-only; a fresh or re-homed cloud session starts full; the full trigger is a missing pacing.json, not the process's first pass.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-10-12T06:19:35+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · wait_until has no owner or schema

Fix: define pacing.json with wait_until, backoff count and next_pass_at; any loop meeting a rate limit writes it; local state dir only.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-10-12T06:19:35+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · Lease safety is a timing argument that fails for small --interval; waits never renew

lease = 3*interval+60 (lease.py:105), --interval min 1s. Fix: cap each sleep at lease expiry minus 5 min and renew; the cloud pass renews before exiting 3 if the lease would lapse.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-10-12T06:19:35+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · 15-minute full pass conflicts with essential-only below the floor

Fix: below the floor a full pass narrows to live-batch repos; align R7 with R10's intersection.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-10-12T06:19:35+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · Per-repo carry breaks cross-repo PR->issue links

invert runs over collected repos' PRs only (collect.py:586). Fix: keep previous links whose PR is in a carried repo; test a cross-repo closing PR both ways.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-10-12T06:19:35+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · Quiet-pass gate misses state changes the driver acts on

Fix: a quiet pass also requires judgements.yaml unchanged since the last planned pass; probe close-out and archive PR heads; list the time-due latencies accepted up to 15 minutes.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-10-12T06:19:35+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · ETag source and probe/collect order unspecified

Fix: probes always precede the repo's collect (unconditional on a full pass); keep only successfully read repos' ETags; test a change interleaved between probe and collect.

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-10-12T06:19:35+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · Rate-limit classification misses GraphQL exhaustion

gh.classify needs 403 (gh.py:672); GraphQL reports 'API rate limit exceeded' with no status. Fix: a text rule over ForgeReadError, Skipped and Unviewed text matching 'rate limit' or RATE_LIMITED.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-10-12T06:19:35+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · Visibility ETag per client instance never hits

make_visibility_client builds a client per push (triage_cmd.py:326). Fix: module-level ETag map keyed by host and repo.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-10-12T06:19:35+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · Snapshot live reads for carried repos not accounted; rate-limited collect continues into snapshot

Fix: a rate-limited collect ends the pass before snapshot; snapshot skips per-batch live reads for carried repos and drops their merge, close-out and archive actions.

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-10-12T06:19:35+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · Kanban watch probes, function name and cloud stretch unspecified

Fix: name _watch (triage_kanban_cmd.py:397), share collect_into probes and pacing.json; the cloud honours the stretch via next_pass_at and exit 3.

<!-- fr:journal kind=finding scope=spec id=sr-13 created=2026-10-12T06:19:35+00:00 state=open review_scope=in -->
### sr-13 · finding [open] (reviewer: in scope) · Verification rows miss R4, R5, R6, R10, R11, R15/R16

Fix: add unit rows quota-secondary-backoff, quota-floor-config, quota-partial-carry, quota-etag-consistency, quota-lease-safe-wait.

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-10-12T06:19:35+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: Quota-held dispatches counted as Summary.held would end the host drive as stalled

Folded into the spec (commit 'fold spec-review findings sr-1..sr-13'): count them as pending, test the proposed-only below-floor case.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-10-12T06:19:35+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: Cloud pass: every drive pass is a first pass; facts.json and probes.json are not on the state ref

Folded into the spec (commit 'fold spec-review findings sr-1..sr-13'): state they are local-only; a fresh or re-homed cloud session starts full; the full trigger is a missing pacing.json, not the process's first pass.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-10-12T06:19:35+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: wait_until has no owner or schema

Folded into the spec (commit 'fold spec-review findings sr-1..sr-13'): define pacing.json with wait_until, backoff count and next_pass_at; any loop meeting a rate limit writes it; local state dir only.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-10-12T06:19:35+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: Lease safety is a timing argument that fails for small --interval; waits never renew

Folded into the spec (commit 'fold spec-review findings sr-1..sr-13'): cap each sleep at lease expiry minus 5 min and renew; the cloud pass renews before exiting 3 if the lease would lapse.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-10-12T06:19:35+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: 15-minute full pass conflicts with essential-only below the floor

Folded into the spec (commit 'fold spec-review findings sr-1..sr-13'): below the floor a full pass narrows to live-batch repos; align R7 with R10's intersection.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-10-12T06:19:35+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: Per-repo carry breaks cross-repo PR->issue links

Folded into the spec (commit 'fold spec-review findings sr-1..sr-13'): keep previous links whose PR is in a carried repo; test a cross-repo closing PR both ways.

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-10-12T06:19:35+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: Quiet-pass gate misses state changes the driver acts on

Folded into the spec (commit 'fold spec-review findings sr-1..sr-13'): a quiet pass also requires judgements.yaml unchanged since the last planned pass; probe close-out and archive PR heads; list the time-due latencies accepted up to 15 minutes.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-10-12T06:19:35+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: ETag source and probe/collect order unspecified

Folded into the spec (commit 'fold spec-review findings sr-1..sr-13'): probes always precede the repo's collect (unconditional on a full pass); keep only successfully read repos' ETags; test a change interleaved between probe and collect.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-10-12T06:19:35+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: Rate-limit classification misses GraphQL exhaustion

Folded into the spec (commit 'fold spec-review findings sr-1..sr-13'): a text rule over ForgeReadError, Skipped and Unviewed text matching 'rate limit' or RATE_LIMITED.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-10-12T06:19:35+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: Visibility ETag per client instance never hits

Folded into the spec (commit 'fold spec-review findings sr-1..sr-13'): module-level ETag map keyed by host and repo.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-10-12T06:19:35+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: Snapshot live reads for carried repos not accounted; rate-limited collect continues into snapshot

Folded into the spec (commit 'fold spec-review findings sr-1..sr-13'): a rate-limited collect ends the pass before snapshot; snapshot skips per-batch live reads for carried repos and drops their merge, close-out and archive actions.

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-10-12T06:19:35+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: Kanban watch probes, function name and cloud stretch unspecified

Folded into the spec (commit 'fold spec-review findings sr-1..sr-13'): name _watch (triage_kanban_cmd.py:397), share collect_into probes and pacing.json; the cloud honours the stretch via next_pass_at and exit 3.

<!-- fr:journal kind=finding scope=spec id=sr-13-resolved created=2026-10-12T06:19:35+00:00 state=fixed resolves=sr-13 -->
### sr-13-resolved · finding [fixed] · resolves sr-13: Verification rows miss R4, R5, R6, R10, R11, R15/R16

Folded into the spec (commit 'fold spec-review findings sr-1..sr-13'): add unit rows quota-secondary-backoff, quota-floor-config, quota-partial-carry, quota-etag-consistency, quota-lease-safe-wait.
