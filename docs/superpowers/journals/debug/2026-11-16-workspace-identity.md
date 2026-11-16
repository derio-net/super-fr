<!-- fr:journal-schema=4 -->
# Journal: 2026-11-16-workspace-identity

<!-- fr:journal kind=repro scope=debug id=d1 created=2026-11-16T18:19:28+00:00 -->
### d1 · repro · Three independent defects, all live on origin/main 4eb40198

#1419: types.branch_slug (types.py:95) maps feat/a__b and feat__a/b to one segment; default_worktree_path, state_path and preserve path key on it. Only quiet/stealth refuse the collision (placement/quiet.py check_feature_id); repo placement does not. #1166: isolation_cmd.up calls _target(repo).up (env-selected) even when a state record exists; carried_state then stamps the env target's mode over the recorded one. #1243: scaffold.py:447/580/592/609 use repo_root.name, which in a linked worktree is the branch slug, not repo_cache_name().
