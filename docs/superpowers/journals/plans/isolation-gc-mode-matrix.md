# Journal: isolation-gc-mode-matrix

<!-- fr:journal kind=decision scope=plan id=d-discovery-sources created=2026-07-27T10:57:30 phase=1 -->
### d-discovery-sources · decision · Discovery proves fr ownership; it never enumerates git worktrees (phase 1)

gc unions docker labels + the fr worktree cache + the invoking repo's fr state records. State records are the only source that sees a workspace at a custom --path or a record whose worktree vanished. `git worktree list` is deliberately NOT consulted, so unrelated automation worktrees are invisible to gc (pinned by test_gc_ignores_unrelated_git_worktree).

<!-- fr:journal kind=decision scope=plan id=d-stale-state-gate created=2026-07-27T10:57:30 phase=1 -->
### d-stale-state-gate · decision · Stale state reap is gated on a healthy docker probe (phase 1)

Retiring a state record whose worktree is gone is safe only when the container view is trustworthy — #354's invariant is that a FAILED `docker ps` must never read as 'no container'. `_stale_state_reapable()` probes `docker ps -q`; docker-less modes override it to True (no containers exist by construction).

<!-- fr:journal kind=decision scope=plan id=d-host-gc-overrides created=2026-07-27T11:00:53 phase=2 -->
### d-host-gc-overrides · decision · Host-worktree gc skips docker steps rather than reimplementing the sweep (phase 2)

Only discovery and teardown were docker-coupled; the merge/content/cleanliness ladder is substrate-neutral. HostWorktreeTarget therefore overrides three seams (_labelled_containers, _sweep_dangling_images, _stale_state_reapable) and inherits the rest, so the two worktree modes cannot drift. The down() override was deleted as redundant once the gc spawn applies to both.

<!-- fr:journal kind=finding scope=plan id=f-ambient-mode-env created=2026-07-27T11:00:53 phase=2 state=fixed -->
### f-ambient-mode-env · finding [fixed] · CLI tests were not hermetic against FR_ISOLATION_TARGET (phase 2)

Eight tests in test_isolation_cmd.py assume devcontainer mode but read the ambient env; on a docker-less pod (which exports FR_ISOLATION_TARGET=worktree) they route to HostWorktreeTarget and fail for environmental reasons. Fixed with an autouse fixture that delenv's the var; mode-specific tests set it explicitly.

<!-- fr:journal kind=decision scope=plan id=d-external-reports created=2026-07-27T11:01:46 phase=3 -->
### d-external-reports · decision · External mode reports rather than refuses (phase 3)

fr cannot honestly reconcile a checkout it does not own, but exit-2-with-no-output left unattended automation with no answer at all. gc now returns exactly one action (verdict=external, action=skipped) naming the preparer as cleanup owner, keeping the --format json contract identical across modes. down deliberately does not fire the opportunistic sweep here.

<!-- fr:journal kind=decision scope=plan id=d-cli-repo-flag created=2026-07-27T11:05:11 phase=4 -->
### d-cli-repo-flag · decision · gc gains --repo and dispatches structurally (phase 4)

The two _refuse_* guards are gone: every target implements gc, so the CLI casts to a small _GcCapable protocol rather than to the worktree family. --repo (via _resolve_repo) lets cron/agent runs name the repo, and turns a deleted cwd into exit 2 with guidance instead of a FileNotFoundError traceback; the detached spawn now passes it explicitly.

<!-- fr:journal kind=discovery scope=plan id=n-preexisting-failures created=2026-07-27T11:05:16 phase=4 -->
### n-preexisting-failures · discovery · Two pre-existing test failures are environmental, not from this branch (phase 4)

tests/integration/test_bridge_project_id.py fails identically on the base commit (a real VK project id reaches the bridge where the fixture expects test-vk-project-id). Verified by stashing this branch's changes and re-running. Unrelated to #423.

<!-- fr:journal kind=discovery scope=plan id=n-live-acceptance created=2026-07-27T11:12:43 phase=5 -->
### n-live-acceptance · discovery · Acceptance signal verified live on this docker-less pod (phase 5)

`FR_ISOLATION_TARGET=worktree fr isolation gc --dry-run --format json` now exits 0 and classifies real workspaces (one open-PR skip, one no-state warn) with no docker present — the exact command the issue quotes as failing. Reaping is still only exercised by tests; spec Test Plan step 2 remains the post-merge live walk.

<!-- fr:journal kind=finding scope=plan id=f-spec-verify-merge-row created=2026-07-27T11:12:43 phase=5 state=fixed -->
### f-spec-verify-merge-row · finding [fixed] · Spec mode matrix wrongly grouped verify-merge with push-check (phase 5)

verify-merge is git + host gh only, so it works in host-worktree mode; only --push-check needs the in-container probe. The matrix row was split rather than left overclaiming a refusal.

<!-- fr:journal kind=finding scope=plan id=f-host-regression-gaps created=2026-07-27T11:15:39 phase=5 state=fixed -->
### f-host-regression-gaps · finding [fixed] · Host-mode regression matrix was missing dirty-skip and content-equivalent (phase 5)

The issue's regression matrix asks for no-PR/content-equivalent handling and a dirty skip in every mode; the first pass only covered them in devcontainer mode, where the shared code path is exercised. Added both as host-mode tests against a real bare origin, plus a gc step in the docker-less end-to-end walk that asserts the sweep classifies the live workspace instead of reaping the run it was launched from.
