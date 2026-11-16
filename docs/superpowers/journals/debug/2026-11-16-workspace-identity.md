<!-- fr:journal-schema=4 -->
# Journal: 2026-11-16-workspace-identity

<!-- fr:journal kind=repro scope=debug id=d1 created=2026-11-16T18:19:28+00:00 -->
### d1 · repro · Three independent defects, all live on origin/main 4eb40198

#1419: types.branch_slug (types.py:95) maps feat/a__b and feat__a/b to one segment; default_worktree_path, state_path and preserve path key on it. Only quiet/stealth refuse the collision (placement/quiet.py check_feature_id); repo placement does not. #1166: isolation_cmd.up calls _target(repo).up (env-selected) even when a state record exists; carried_state then stamps the env target's mode over the recorded one. #1243: scaffold.py:447/580/592/609 use repo_root.name, which in a linked worktree is the branch slug, not repo_cache_name().

<!-- fr:journal kind=decision scope=debug id=d2 created=2026-11-16T18:22:29+00:00 decided_by=operator -->
### d2 · decision · Fix all three defects separately, one PR

Operator chose: three independent fixes, each failing-test-first, one draft PR. #1419 refuses a colliding branch at up (slug format unchanged, no migration); #1166 routes a resume through the recorded mode; #1243 uses repo_cache_name().

<!-- fr:journal kind=root-cause scope=debug id=d3 created=2026-11-16T18:25:44+00:00 -->
### d3 · root-cause · Identity taken from a stand-in, in three places

#1419: state_path/default_worktree_path key on a non-injective slug and nothing compared the record's own branch. #1166: isolation_cmd.up always called the env-selected _target, and carried_state stamps the caller's mode. #1243: scaffold used repo_root.name, the worktree folder, where repo_cache_name() names the main checkout.

<!-- fr:journal kind=finding scope=debug id=d4 created=2026-11-16T21:20:15+00:00 state=fixed -->
### d4 · finding [fixed] · Three fixes, each pinned by a failing-first test

types.slug_holder/check_slug_free + load_state/delete_state ignore another branch's record, check called from _worktree_up_core (gh#1419); isolation_cmd._up_target routes a recorded workspace through _target_for (gh#1166); scaffold uses repo_cache_name() for name, runArgs, env file and placeholder (gh#1243). Tests: tests/unit/test_workspace_identity.py (4). Full suite: 16280 passed, 9 failed in test_isolation_agent_worktrees.py under host load ~14 over a 2h44m run; that file passes alone (19/19) and the isolation set in parallel (876/876); it uses none of the changed symbols.
