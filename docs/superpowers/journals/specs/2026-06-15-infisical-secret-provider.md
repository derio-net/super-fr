# Journal: 2026-06-15-infisical-secret-provider

<!-- fr:journal kind=decision scope=spec id=q-mode-scope created=2026-09-14T16:33:45 -->
### q-mode-scope · decision · Infisical --secret is devcontainer-mode only

Operator Q&A 2026-09-14. main split isolation into devcontainer / host-worktree / external targets after this spec. Injection is implemented for devcontainer (the docker substrate); in host-worktree and external modes --secret fails fast with an actionable IsolationError — those modes carry ESO-injected env already. env-file profiles unchanged everywhere.

<!-- fr:journal kind=decision scope=spec id=q-live-smoke created=2026-09-14T16:33:46 -->
### q-live-smoke · decision · Live Infisical smoke stays back-loaded to the operator

Operator Q&A 2026-09-14. frank (and its infisical namespace) is reachable again, but the host has no infisical CLI and no FR_INFISICAL_* vars. The PR ships the [manual] live-smoke phase unimplemented; the operator provisions the read-only short-TTL UA identity and records it with fr plan edit --complete-phase.

<!-- fr:journal kind=decision scope=spec id=q-pr-vehicle created=2026-09-14T16:33:48 -->
### q-pr-vehicle · decision · Rebase feat/secrets-injection onto main and force-push to PR #314

Operator Q&A 2026-09-14, per #333 checklist. Keeps the review history; the stale worktree (no marker, dead container) was torn down and recreated.

<!-- fr:journal kind=decision scope=spec id=q-hard-tier created=2026-09-14T16:33:49 -->
### q-hard-tier · decision · Hard-tier phases dispatch on Fable 5.1 for this run

Operator chose claude-fable-5-1 for the top tier. The question named it strong; the claude-code harness top tier is hard, already bound to opus in ~/.config/fr/models.yaml. Binding left untouched (premise was wrong); honored per-dispatch instead.

<!-- fr:journal kind=decision scope=spec id=rebase-tactic created=2026-09-14T16:33:51 -->
### rebase-tactic · decision · Rebuild Target wiring as a new TDD phase instead of hand-splicing rebase conflicts

Commits 6/8/9 conflicted with main 4.x (local.py split into three targets, 180-line misaligned hunks). Took main side for local.py, isolation_cmd.py and the two skill docs in those commits; secrets.py, scaffold, tests and plan ticks landed. The carried test_secrets_wiring.py (7 red) is the new phase RED. scaffold/init_cmd conflicts were unions (backend/host + secret_provider/infisical) and were resolved by hand; env-file ensure ported to post-#408 behavior (vk mount raises, harden_secret_file).

<!-- fr:journal kind=review scope=spec id=spec-review-2026-09-14 created=2026-09-14T16:37:06 -->
### spec-review-2026-09-14 · review · Spec reviewed against Q&A answers and the 4.x codebase

Findings, each fixed in the spec (Re-integration addendum + new Test Plan): (1) spec predates the host-worktree and external targets — added the devcontainer-only scope decision and Target.exec(keys). (2) SecretProvider had grown post_exec/cleanup in code but not in the spec — documented. (3) §3 required serialized or per-exec token files; the branch shipped only a NOTE — specified a bind-mounted token DIRECTORY with per-exec 0600 files (also avoids the single-file bind-mount inode trap). (4) 4.x down is a shared tail — pinned provider cleanup inside the devcontainer _teardown_container (after the PR guard, before worktree removal). (5) no ## Test Plan, which the acceptance staleness guard needs — added six items mapped 1:1 to matrix rows. Verified names exist: LocalWorktreeDevcontainerTarget, HostWorktreeTarget, ExternalTarget, _teardown_container, _down_worktree_tail, harden_secret_file, profiles_config, _target_or_exit.

<!-- fr:journal kind=decision scope=spec id=skeleton-override-2026-06-15-infisical-secret-provider created=2026-09-14T16:37:44 -->
### skeleton-override-2026-06-15-infisical-secret-provider · decision · No walking-skeleton marker on phase 1 (completed 2026-06-15)

Phase 1 shipped in June, before the skeleton convention existed, and was green in CI then. Adding skeleton: true now would claim a smoke that never ran. The delivery infrastructure this plan needs (pytest, ruff, mypy, the devcontainer) is exercised by the full-gate baseline run on 2026-09-14 (2914 passed) before phase 5 starts.
