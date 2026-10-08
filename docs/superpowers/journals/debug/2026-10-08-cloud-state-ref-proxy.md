# Journal: 2026-10-08-cloud-state-ref-proxy

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-08T20:52:23+00:00 -->
### repro · repro · fr triage collect exits 2 in a cloud session: the state ref push is refused

Walk 16 (spec 2026-10-07-cloud-triage Test Plan 16), cloud session, main at 29cdcd9e, forge.api: rest, fresh clone: `fr triage collect --repo derio-net/super-fr` wrote facts.json (48 open issues, no GraphQL call) then failed: `git push --force-with-lease=refs/fr/triage/s-22ba5885: ... 014d2c74:refs/fr/triage/s-22ba5885` -> `RPC failed; HTTP 403`, exit 2.

<!-- fr:journal kind=hypothesis scope=debug id=h1 created=2026-10-08T20:52:24+00:00 -->
### h1 · hypothesis · The cloud git proxy refuses pushes outside refs/heads/

Probes from this session: push to refs/heads/fr-triage/walk16-probe and refs/heads/feat/cloud-triage-walk16-probe created both branches; a non-fast-forward --force-with-lease update of refs/heads/fr-triage/walk16-probe succeeded (forced update); deleting either branch by push (:ref) hung up; REST POST/DELETE repos/derio-net/super-fr/git/refs (refs/fr/triage/walk16-probe, refs/heads/...) answered 403 'Write access to this GitHub API path is not permitted through this proxy'. So: refs/heads/* create + force-update allowed; refs outside refs/heads/, branch deletion and REST ref writes refused. Confirmed.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-10-08T20:52:26+00:00 -->
### root-cause · root-cause · The state ref lives outside refs/heads/, which the cloud git proxy refuses to write; a refused push fails the whole collect

state_ref.REF_PREFIX = refs/fr/triage/ (spec R5 chose a non-branch ref so it shows in no branch list and no PR); spec s12 recorded the proxy behaviour as unmeasured and the walk is the first measurement. Separately, collect treats the ref push as fatal after facts.json is already written. Operator decision (2026-10-08): move the ref to refs/heads/fr-triage/<scope-id>, keep reading the old ref for migration, and make a refused push a warning.

<!-- fr:journal kind=finding scope=debug id=fix-ref-under-heads created=2026-10-08T21:01:03+00:00 state=fixed -->
### fix-ref-under-heads · finding [fixed] · The state ref is the orphan branch refs/heads/fr-triage/<scope-id>, read from the legacy refs/fr/triage/ ref for migration

9977b898. state_ref.REF_PREFIX = refs/heads/fr-triage/, legacy_ref_name for refs/fr/triage/; fetch_state falls back to the legacy ref and records it as the base's ref, so the first push creates the branch (expected-old absent); the legacy ref is never deleted; gitseam.fetch_ref keeps fetched refs under refs/fr/fetched/ so the workspace's branch list never shows the state branch. Tests (tests/unit/test_triage_state_ref.py): test_the_state_ref_is_a_branch_under_refs_heads, test_the_state_branch_is_an_orphan_sharing_no_history_with_the_code, test_fetch_restores_from_the_legacy_ref_when_the_branch_is_absent, test_a_legacy_base_is_not_the_expected_old_of_the_first_branch_push, test_the_branch_wins_over_the_legacy_ref_when_both_exist, test_a_fetch_never_creates_a_branch_in_the_workspace; scenarios cloud-triage-state-ref/driver-lease/version-drift read refs/heads/fr-triage/.

<!-- fr:journal kind=finding scope=debug id=fix-refused-push-warns created=2026-10-08T21:01:05+00:00 state=fixed -->
### fix-refused-push-warns · finding [fixed] · A push the remote refuses is a warning after a command's own work, not exit 2; a lease conflict still fails

9977b898. gitseam.push_ref_cas: git exits 1 for both a lost lease and a refusal, so a lease is told by git's '(stale info)' or, failing that, a remote ref that moved; a ref that did not move (or cannot be read) raises PushRefused. push_state wraps it as StateRefPushRefused (not a StateRefConflict). triage_cmd._push_if_changed prints 'warning: <ref> was not pushed; the state stays local until a push succeeds ...' and exits 0; fr triage state push, the lease and the drive still exit 2. Tests: test_a_push_the_remote_refuses_is_a_refusal_not_a_conflict, test_a_refused_push_over_an_existing_ref_is_still_a_refusal, test_push_ref_cas_tells_a_stale_lease_from_a_refusal (pre-receive hook refusing on a bare remote), and in tests/unit/test_triage_state_ref_sync.py test_collect_whose_push_is_refused_warns_and_exits_zero, test_a_wrapped_command_whose_push_is_refused_warns_and_exits_zero, test_state_push_whose_push_is_refused_still_fails.

<!-- fr:journal kind=review scope=debug id=review created=2026-10-08T21:03:23+00:00 -->
### review · review · Orchestrator review of the fix: no findings

Reviewed the diff of gitseam.py, state_ref.py and triage_cmd.py against the root cause. A stale lease is still recognised by git's '(stale info)', or failing that by re-reading the remote ref, so a lost race stays StateRefConflict. A refusal leaves the ref unmoved and becomes StateRefPushRefused. A legacy-ref base is recorded under the legacy name, so the first push to the branch uses expected-old None. Only _push_if_changed downgrades a refusal to a warning; state push, the lease and drive pushes still fail. Fetched refs are kept under refs/fr/fetched/, so the workspace never gains a local fr-triage branch. Findings raised: none. Not live-proven yet: the walk 16 rerun against this build is owed.
