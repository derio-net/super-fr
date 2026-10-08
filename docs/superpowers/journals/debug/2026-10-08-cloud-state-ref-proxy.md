# Journal: 2026-10-08-cloud-state-ref-proxy

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-08T20:52:23+00:00 -->
### repro · repro · fr triage collect exits 2 in a cloud session: the state ref push is refused

Walk 16 (spec 2026-10-07-cloud-triage Test Plan 16), cloud session, main at 29cdcd9e, forge.api: rest, fresh clone: `fr triage collect --repo derio-net/super-fr` wrote facts.json (48 open issues, no GraphQL call) then failed: `git push --force-with-lease=refs/fr/triage/s-22ba5885: ... 014d2c74:refs/fr/triage/s-22ba5885` -> `RPC failed; HTTP 403`, exit 2.
