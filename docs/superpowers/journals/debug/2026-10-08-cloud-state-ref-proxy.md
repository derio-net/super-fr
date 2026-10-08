# Journal: 2026-10-08-cloud-state-ref-proxy

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-08T20:52:23+00:00 -->
### repro · repro · fr triage collect exits 2 in a cloud session: the state ref push is refused

Walk 16 (spec 2026-10-07-cloud-triage Test Plan 16), cloud session, main at 29cdcd9e, forge.api: rest, fresh clone: `fr triage collect --repo derio-net/super-fr` wrote facts.json (48 open issues, no GraphQL call) then failed: `git push --force-with-lease=refs/fr/triage/s-22ba5885: ... 014d2c74:refs/fr/triage/s-22ba5885` -> `RPC failed; HTTP 403`, exit 2.

<!-- fr:journal kind=hypothesis scope=debug id=h1 created=2026-10-08T20:52:24+00:00 -->
### h1 · hypothesis · The cloud git proxy refuses pushes outside refs/heads/

Probes from this session: push to refs/heads/fr-triage/walk16-probe and refs/heads/feat/cloud-triage-walk16-probe created both branches; a non-fast-forward --force-with-lease update of refs/heads/fr-triage/walk16-probe succeeded (forced update); deleting either branch by push (:ref) hung up; REST POST/DELETE repos/derio-net/super-fr/git/refs (refs/fr/triage/walk16-probe, refs/heads/...) answered 403 'Write access to this GitHub API path is not permitted through this proxy'. So: refs/heads/* create + force-update allowed; refs outside refs/heads/, branch deletion and REST ref writes refused. Confirmed.
