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
