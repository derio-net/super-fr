# Journal: isolation-gc-mode-matrix

<!-- fr:journal kind=decision scope=plan id=d-discovery-sources created=2026-07-27T10:57:30 phase=1 -->
### d-discovery-sources · decision · Discovery proves fr ownership; it never enumerates git worktrees (phase 1)

gc unions docker labels + the fr worktree cache + the invoking repo's fr state records. State records are the only source that sees a workspace at a custom --path or a record whose worktree vanished. `git worktree list` is deliberately NOT consulted, so unrelated automation worktrees are invisible to gc (pinned by test_gc_ignores_unrelated_git_worktree).

<!-- fr:journal kind=decision scope=plan id=d-stale-state-gate created=2026-07-27T10:57:30 phase=1 -->
### d-stale-state-gate · decision · Stale state reap is gated on a healthy docker probe (phase 1)

Retiring a state record whose worktree is gone is safe only when the container view is trustworthy — #354's invariant is that a FAILED `docker ps` must never read as 'no container'. `_stale_state_reapable()` probes `docker ps -q`; docker-less modes override it to True (no containers exist by construction).
