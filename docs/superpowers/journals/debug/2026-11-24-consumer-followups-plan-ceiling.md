<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-consumer-followups-plan-ceiling

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-11-24T18:47:12+00:00 -->
### repro-1 · repro · CI red on PR #1583: test_install_opencode_agents binding tests find no model: line

Run 45129737281 (head 08a91cf6e, merge ref with main 0bf258293 = release v9.0.0-rc.1): test_a_resolved_binding_lands_as_model_on_each_tier_file_only and test_an_unbound_tier_inherits_rather_than_pinning_an_empty_model fail, no `model:` on any tier file. Both pass locally in the worktree. Repro: rebuild 08a91cf6e+0bf258293 in a detached clone and run `fr models apply --harness opencode` with cwd=checkout, env -i (HOME/XDG/PATH only), stdin not a TTY: rc=2, 'artifacts ... must be migrated', HEAD detached.

<!-- fr:journal kind=ruled-out scope=debug id=h-staleness-validate created=2026-11-24T18:47:15+00:00 -->
### h-staleness-validate · ruled-out · fr validate artifacts on the merged tree reports all valid, so the stale artifact is not visible there

A 9.0.0rc ceiling check admits '<9.0.0' (an RC sorts below the final), so validate passes; the CLI-entry gate's ceiling repair instead asks whether the ceiling admits the installed MAJOR. The two disagree; the gate is what install.sh hits.

<!-- fr:journal kind=root-cause scope=debug id=rc-1 created=2026-11-24T18:47:18+00:00 -->
### rc-1 · root-cause · The branch's own plan carries fr_version <9.0.0; main's 9.0.0-rc release made it stale, and install.sh swallows fr's refusal

docs/superpowers/plans/2026-11-19-consumer-followups/_meta.yaml: fr_version '>=4.20.0,<9.0.0'. The v9.0.0-rc.1 release's migrate widened only plans on main. On the PR merge ref the gate wants to widen this one, but the test's install.sh runs in the refuse context (detached HEAD, no CI var in its env, no TTY, no isolation marker), so `fr models apply` exits 2 and `|| true` hides it. Locally the worktree is a valid workspace, where the gate migrates silently, so the tests pass.
