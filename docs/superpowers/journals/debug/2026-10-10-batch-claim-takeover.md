# Journal: 2026-10-10-batch-claim-takeover

<!-- fr:journal kind=repro scope=debug id=46a39cd2aaa9 created=2026-10-10T18:10:48+00:00 -->
### 46a39cd2aaa9 · repro · Expired foreign claim cannot be taken over through the CLI (gh#1120)

batch create/edit refuse a member held by another scope, expired or live (_refuse_held -> held_map/holder, R5). claim take requires the key to already be a member of one of this scope's batches (triage_claim_cmd.py claim_take_command). held_line's expired-hint names claim take, which cannot succeed. Read from code at aaeea750; matches the live repro in gh#1120.
