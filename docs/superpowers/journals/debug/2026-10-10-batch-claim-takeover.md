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
