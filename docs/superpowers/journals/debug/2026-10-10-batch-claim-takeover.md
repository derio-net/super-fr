# Journal: 2026-10-10-batch-claim-takeover

<!-- fr:journal kind=repro scope=debug id=46a39cd2aaa9 created=2026-10-10T18:10:48+00:00 -->
### 46a39cd2aaa9 · repro · Expired foreign claim cannot be taken over through the CLI (gh#1120)

batch create/edit refuse a member held by another scope, expired or live (_refuse_held -> held_map/holder, R5). claim take requires the key to already be a member of one of this scope's batches (triage_claim_cmd.py claim_take_command). held_line's expired-hint names claim take, which cannot succeed. Read from code at aaeea750; matches the live repro in gh#1120.

<!-- fr:journal kind=repro scope=debug id=37ffd5bd3353 created=2026-10-10T18:10:55+00:00 -->
### 37ffd5bd3353 · repro · A taken claim on a wave-less proposed batch is not owed, so claim sync releases it

owed_claims owes a claim only with a wave or from dispatched on (_owes). plan_sync passes this scope's own open-issue claims to owed_releases(own=...), which lists every own claim no batch owes for release. A claim from claim take on a wave-less proposed batch is therefore neither refreshed nor kept: the next claim sync --yes / drive --yes releases it. Worse than gh#1120's guess (lapse in 24h).

<!-- fr:journal kind=hypothesis scope=debug id=e0d071fe3810 created=2026-10-10T18:11:05+00:00 -->
### e0d071fe3810 · hypothesis · gh#1123 is a separate root cause from gh#1120

gh#1120 (both halves) is one cause: claim take writes a claim outside R3's owed-claims model, and R5 has no expired-holder path into a batch. gh#1123 is a different gap: R9 accepts only expiry as evidence a holder is gone, with no operator override for a stale (R8) claim. Fixing gh#1120 does not touch R9's liveness test, and gh#1123 needs new verbs (scope retire, take/release --stale). Per the batch's debugging rules, stopping to ask before fixing either.

<!-- fr:journal kind=decision scope=debug id=c6e9f7ad26a4 created=2026-10-10T18:29:49+00:00 -->
### c6e9f7ad26a4 · decision · Operator: fix both in one PR; a take records a claim_taken event

Operator answered 2026-10-10: fix gh#1120 and gh#1123 in the one PR, as separate commits. A taken claim on a wave-less batch stays owed through a new claim_taken batch event (auditable, matches the events model), accepting the judgements schema bump.

<!-- fr:journal kind=root-cause scope=debug id=9c77dc8ecc39 created=2026-10-10T18:44:09+00:00 -->
### 9c77dc8ecc39 · root-cause · gh#1120: R5 admits no held member, and R3 owes no claim the operator took

batch create/edit refused every foreign-held member (live or expired), while claim take needs batch membership; and owed_claims (R3) owed a claim only by wave or dispatch, so plan_sync's owed_releases(own=...) released a claim taken onto a wave-less proposed batch at the next sync.

<!-- fr:journal kind=root-cause scope=debug id=ad29fa5ddc7b created=2026-10-10T18:44:39+00:00 -->
### ad29fa5ddc7b · root-cause · gh#1123: R9 accepts only expiry as evidence a holder is gone

claim take/release judged a foreign claim displaceable only once expired; R8's staleness (heartbeat older than a quarter of the marker's own expiry window) was never consulted, and no verb released a whole scope.

<!-- fr:journal kind=decision scope=debug id=d7906d30ed08 created=2026-10-10T18:45:07+00:00 -->
### d7906d30ed08 · decision · create/edit admit a STALE-held member, not only an expired one

take --stale needs the issue in a batch of this scope, exactly as take did; admitting only expired members would rebuild gh#1120's deadlock for --stale. Admission writes no claim and R6 still blocks dispatch/merge/drive until the take, so a holder that is merely slow loses nothing it can act on. A FRESH foreign claim is still refused (R5).

<!-- fr:journal kind=decision scope=debug id=3e5eb21923d8 created=2026-10-10T18:45:37+00:00 -->
### 3e5eb21923d8 · decision · Staleness is judged from the marker alone

stale(c) = expired, or now - heartbeat > (expires - heartbeat)/4, using the expiry window the marker states. R8 already says every reader judges expiry from the marker; this extends that to staleness, so a scope with a different claim_expiry_hours is judged by its own window. The released marker's human line now says expired / gone stale / retired by the operator, from the marker's own timestamps (no JSON change).

<!-- fr:journal kind=finding scope=debug id=5287f428e9b7 created=2026-10-10T19:10:04+00:00 state=fixed -->
### 5287f428e9b7 · finding [fixed] · Takeover reachable, taken claims owed, stale override and scope retire

claims.py (taken_keys, stale, held_line hint), claim_writes.py (allow=expired|stale|any via may_displace), triage_batch_cmd.py (_admit_held, _say_takes), triage_claim_cmd.py (take/release --stale, claim_taken event, scope retire), model.py (ClaimTakenEvent, judgements schema 8). Pinned by the gh#1120/gh#1123 tests in test_triage_claim_cmd.py, test_triage_claim_writes.py, test_triage_claims.py and the rewritten triage-claims-expired scenario. Full suite NOT run locally (operator instruction: host overloaded); PR CI is the evidence.

<!-- fr:journal kind=review scope=debug id=f1b2a36c6770 created=2026-10-10T19:11:02+00:00 -->
### f1b2a36c6770 · review · Self-review of the diff: one finding fixed, one noted

Fixed: batch edit --no-wave on a proposed batch released every member's claim, including a taken one, which the next sync would re-claim (churn). It now keeps taken keys (test_no_wave_keeps_a_taken_members_claim). Noted, not changed: claim take writes the forge before appending claim_taken; if that judgements write fails, the claim stands without the event and the next sync releases it. Same ordering as claim sync's claims_released record; the take can be re-run. No independent reviewer subagent was dispatched.
