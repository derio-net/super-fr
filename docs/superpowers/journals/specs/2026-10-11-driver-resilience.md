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
