# Live post-merge close-out: #1089

Observed 2026-10-10 in a new OpenCode 1.18.35 session, model
`openai/gpt-6.1-sol`, inside Herdr 0.9.0 (client/server protocol 22).
Paths and session identifiers are redacted. This is an agent-driven live
close-out under the operator's explicit instruction, not a synthetic scenario.

## Pickup and merge gates

- From the stable primary checkout, `git pull --ff-only` brought in PR #1115,
  merge commit `ce7974a27ff627221d71931d4592c76bead3548b`.
- The exact `fr pickup --run 2026-10-09-feat-1089` returned its merged-PR
  close-out brief, rather than redispatching implementation or replaying the goal.
- The first merge verification failed because a stale isolation record pointed
  at an already removed feature worktree. The session stopped at that gate;
  no passing evidence or issue closure was claimed.
- After the operator reconciled that stale record, the same gate passed:
  `verify-merge: feat/1089 ✓ changes present on origin/main, PR MERGED.
  (workspace already reaped; checked from the repo root)`.

## Feature workspace and session cleanup

- `fr isolation status --branch feat/1089 --format json` reports no workspace.
  `fr isolation down --branch feat/1089` likewise reports no workspace to remove.
- Docker's all-container query filtered by the feature worktree's
  `devcontainer.local_folder` label returned no containers.
- The old feature session's fr session-index file is absent.
- Herdr still showed the delivered `request-1089-resumed` OpenCode session idle
  in its old, removed worktree. Under the requested session-cleanup scope,
  `herdr tab close` on that session's exact tab succeeded. A subsequent
  `herdr agent get request-1089-resumed` returned `agent_not_found`.
- Before and after feature-session cleanup, `herdr pane current --current`
  observed this fresh `closeout1089` OpenCode control session with both cwd and
  foreground cwd at the stable primary checkout. The control session survived
  the feature workspace's removal and the delivered session's tab cleanup.
  The active reporting tab is retained to deliver the result to the operator.

## Scoped archive

- `fr status` and the spec rollup confirmed both phases complete on origin/main.
- Created only `chore/archive-2026-10-09-herdr-opencode-replacement` via fr isolation.
- In that workspace, the branch-scoped `fr archive --branch feat/1089` archived
  the plan, spec, run, usage, plan/spec journals and both associated debug journals.
  All eight artifact groups were archived; none was held.
- The pickup-selected storage finding was filed as #1117 and deferred in its
  archived journal. Existing native-model-fallback deferral to #1116 was preserved.
- The CLI retargeted the five related acceptance origins and regenerated all
  three acceptance reports. Usage capture honestly reports missing dollars;
  no cost completeness is claimed.

The archive and this evidence are published through a housekeeping PR. Acceptance
status remains `skipped` because this real walk is not automated in CI. No wave
driver was started or operated. No conflict resolution, native effective-model
fallback fix, or new implementation behavior is claimed.
