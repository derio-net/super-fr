<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-consumer-followups-plan-ceiling

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-11-24T18:47:12+00:00 -->
### repro-1 · repro · CI red on PR #1583: test_install_opencode_agents binding tests find no model: line

Run 45129737281 (head 08a91cf6e, merge ref with main 0bf258293 = release v9.0.0-rc.1): test_a_resolved_binding_lands_as_model_on_each_tier_file_only and test_an_unbound_tier_inherits_rather_than_pinning_an_empty_model fail, no `model:` on any tier file. Both pass locally in the worktree. Repro: rebuild 08a91cf6e+0bf258293 in a detached clone and run `fr models apply --harness opencode` with cwd=checkout, env -i (HOME/XDG/PATH only), stdin not a TTY: rc=2, 'artifacts ... must be migrated', HEAD detached.
