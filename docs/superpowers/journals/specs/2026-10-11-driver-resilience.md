<!-- fr:journal-schema=2 -->
# Journal: 2026-10-11-driver-resilience

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-11T17:07:44+00:00 input=true -->
### operator-brief · discovery · Batch driver-resilience brief (super-fr#1127, #1134, #1135), verbatim

/fr-goal Drive loop resilience: no silent single pass, retry transient visibility reads, REST free-plan 403

Batch `driver-resilience` of derio-net/super-fr: 3 issues, delivered as ONE pull request.

## super-fr#1127: drive: refuse --once --yes that dispatches when no looping driver is running
Observed in this scope on 2026-10-10: two `drive --once --yes` passes dispatched wave 1 and left nothing driving (no merges, stale board) until the loop was started by hand.

## super-fr#1134: drive: a transient failure reading the state repo's visibility ends a looping driver (should skip the pass and retry)
Filed from this scope. `privacy.unreadable()` (`fr/triage/privacy.py:50`) raises on a transient rate-limit read, which ends a looping driver instead of skipping the pass.

## super-fr#1135: REST forge: the rulesets endpoint's free-plan 403 on a private repo makes every drive pass fail
Filed from this scope. `required_check_names` (`fr/real_ghrestclient.py:731`) reads `rules/branches/{b}` unconditionally; the free-plan 403 on a private repo fails every REST drive pass.

## Why these belong together
All three stopped or stalled this scope's wave-1 driver on 2026-10-10.

## Delivery rules
- Work on branch `feat/batch-driver-resilience`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1127
  Closes derio-net/super-fr#1134
  Closes derio-net/super-fr#1135
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=visibility-no-cache created=2026-10-11T17:07:44+00:00 -->
### visibility-no-cache · decision · #1134: no visibility cache; cloud-triage R8's live read stands

Operator chose no cache (recommended). Caching a 'private' answer is the leak direction; skip-and-retry alone fixes the exit, at ~2 REST reads per pass.

<!-- fr:journal kind=decision scope=spec id=visibility-skip-any-unreadable created=2026-10-11T17:07:44+00:00 -->
### visibility-skip-any-unreadable · decision · #1134: loop mode skips the pass on ANY unreadable state-repo visibility

Operator chose any cause (recommended) over classifying transient errors. Still fail-closed: nothing is written or pushed. --once, plan mode and the cloud pass keep exit 2.

<!-- fr:journal kind=decision scope=spec id=rulesets-403-silent created=2026-10-11T17:07:44+00:00 -->
### rulesets-403-silent · decision · #1135: the free-plan rulesets 403 is treated as no rulesets, silently

Operator chose silent (recommended): it is a definitive answer, not a degraded read.

<!-- fr:journal kind=decision scope=spec id=verification-unit-only created=2026-10-11T17:07:44+00:00 -->
### verification-unit-only · decision · Verification: unit tests only, rows verify: none, no walk

Operator chose unit tests only (recommended). The forge conditions (rate limit, free-plan 403) cannot be produced on demand; fakes are the proof.

<!-- fr:journal kind=discovery scope=spec id=once-already-sole-driver created=2026-10-11T17:07:44+00:00 -->
### once-already-sole-driver · discovery · #1127's 'no looping driver' condition is implied by drive_lock + the lease

batch_drive_command takes drive_lock for --once too, and --yes takes the state-ref lease; both refuse a second driver. So a --once --yes pass that reaches its plan is the scope's only driver on this host/lease, and the guard reduces to 'the plan holds a dispatch'.

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-10-11T17:14:32+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · Loop-mode skip after a failed save_pass bypasses restart_to, so the next pass runs on stale code (gh#998)

_host_loop's ForgeReadError branch sleeps and continues before the restart_to check; a skipped save_pass after a post_merge that reinstalled fr would run another pass on old code. The spec must return restart_to there, and a test must pin it.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-10-11T17:14:32+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · R9 says plan mode 'keeps refusing' on unreadable visibility, but plan mode never reads it

Without --yes there is no lease, take_lease returns early and save_pass never runs, so no guard_state call happens. The requirement is vacuous and untestable.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-10-11T17:14:32+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · --single-pass warning keyed on 'plan holds a dispatch' (R4) vs 'the pass dispatched' (Design); driver state not named

A planned dispatch may not start (held claim, preflight refusal, RunnerDispatchError). Pick one condition, and name the build_driver parameter and the memo so 'cloud pass unaffected by construction' can be checked.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-10-11T17:14:32+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · R1 breaks existing --once --yes tests whose plan dispatches; the spec does not say they gain --single-pass

Many host tests drive a dispatching --once --yes pass (test_triage_batch_drive_cmd.py and siblings); after R1 they exit 2 unless they pass --single-pass.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-10-11T17:14:32+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · The printed loop command does not pin a single-repo scope's defaulted checkout

With no --checkout, a single-repo scope defaults to the cwd's toplevel; a pasted command in another pane would drive a different clone.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-10-11T17:14:32+00:00 state=open review_scope=out -->
### sr-6 · finding [open] (reviewer: out of scope) · A transient failure reading a member repo's visibility (public state repo) is reported as a leak and still ends a looping driver

guard_state's _fill turns a failed member-repo read into None, which counts as not public and raises the plain leak refusal. Pre-existing; R8 and the operator decision are scoped to the state repo's own visibility.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-10-11T17:14:32+00:00 -->
### spec-review-1 · review · independent spec review: 6 findings (5 in, 1 out)

fr-spec-reviewer checked the spec against the four operator decisions (all honoured) and the codebase: build_driver/_Driver callers, ForgeReadError exit codes under --once and the cloud pass, check_or_refuse reachability (inert in the driver), the GhError 403 text (gh.py:194-204), and lease release before _fail (no conflict). Findings sr-1..sr-5 in scope, sr-6 out of scope.

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-10-11T17:14:32+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: Loop-mode skip after a failed save_pass bypasses restart_to, so the next pass runs on stale code (gh#998)

R8 and §B now say: _host_loop's ForgeReadError branch returns driver.restart_to when it is set, instead of sleeping.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-10-11T17:14:32+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: R9 says plan mode 'keeps refusing' on unreadable visibility, but plan mode never reads it

R9 drops plan mode and states that it never reads the visibility; the §B bullet now names --once only.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-10-11T17:14:32+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: --single-pass warning keyed on 'plan holds a dispatch' (R4) vs 'the pass dispatched' (Design); driver state not named

Both R1 and R4 key on the plan holding a dispatch. Named: build_driver(single_pass: SinglePass(notice, allowed)) and _Driver.planned_dispatch; the cloud pass never passes it.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-10-11T17:14:32+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: R1 breaks existing --once --yes tests whose plan dispatches; the spec does not say they gain --single-pass

§A now states that the existing dispatching --once --yes host tests add --single-pass, and that non-dispatching tests stay as they are and pin R5.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-10-11T17:14:32+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: The printed loop command does not pin a single-repo scope's defaulted checkout

R3 and §A print a single-repo scope's defaulted checkout explicitly as --checkout OWNER/REPO=<abs toplevel>, taken from _checkout_map.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-10-11T17:14:32+00:00 state=open resolves=sr-6 out_of_scope=true -->
### sr-6-resolved · finding [out-of-scope] · resolves sr-6: A transient failure reading a member repo's visibility (public state repo) is reported as a leak and still ends a looping driver

Not caused by this change: the member-repo live read and its leak-refusal wording predate it, and the operator scoped #1134 to the state repo's own visibility. To file as its own issue.
