<!-- fr:journal-schema=3 -->
# Journal: 2026-10-24-ops-archived-plan-trust

<!-- fr:journal kind=repro scope=debug id=archived-trust-refusal created=2026-10-24T20:53:46+00:00 -->
### archived-trust-refusal · repro · Archived plans cannot receive an ops trust grant

RC9 grant_trust() checks only docs/superpowers/plans/<slug>, so an otherwise loadable plan under implemented/plans fails at confirmation. The audit writer also always targets the active journal; an archived audit there makes the repo appear dirty to trust fingerprint validation. Reproduced and fixed with isolated temporary repositories and test-local trust directories only; no production fixture trust or probes used.
