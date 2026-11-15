<!-- fr:journal-schema=4 -->
# Journal: 2026-11-15-guard-trust

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-15T16:55:37+00:00 input=true -->
### brief · discovery · Operator brief (batch guard-trust, verbatim)

/fr-goal Guards that switch off or trust the wrong binary

Batch `guard-trust` of derio-net/super-fr: 5 issues, delivered as ONE pull request.

## super-fr#1277: Archiving the last live plan silently disables the fr-isolation edit gate on fresh checkouts (repos without a devcontainer profile)
Live: the fr-enabled test is still a bare directory check, now at `plugins/super-fr/hooks/lib/fr-isolation-decision.sh:332` (was :192) and `packages/fr-opencode-plugin/src/marker.ts:273` (was :69). `fr archive` (`packages/fr/src/fr/archive.py:460` `archive_plan_dir`) does not leave a `.gitkeep`. After the last live plan is archived, the edit gate silently turns off on fresh clones of repos with no devcontainer profile. super-fr only escapes through its own committed `docs/superpowers/plans/.gitkeep`.
Note: Guard change: per memory, get an independent adversarial review before merge. Fix in both the archive (keep a `.gitkeep`) and the gate (e.g. accept `docs/superpowers/implemented/plans`).

## super-fr#1429: hooks: git lookup and bare fr spawns still trust relative PATH entries
Still live; a planted-binary hole. `fr_git_resolve` in `hooks/lib/fr-isolation-decision.sh:163` uses `command -v` for non-absolute candidates. `onPath` in `fr-opencode-plugin/src/git.ts:55-62` accepts relative PATH dirs. `hooks/fr-worktree-create.sh:59-60` and `src/pin.ts:39` (`run("fr", ...)`) still spawn `fr` by name.
Note: The pattern to copy is `fr_fr_resolve` / `resolveFr`. Bundle with super-fr#1279 (hooks).

## super-fr#1230: file_lock.py and fr_herdr managed.py spawn python -c 'import fcntl' with an inherited cwd
Still live. `packages/fr/src/fr/file_lock.py:31-37` and `packages/fr-herdr/src/fr_herdr/managed.py:134-142` run `sys.executable -c 'import fcntl...'` without `-I`/`-P`. A `fcntl.py` planted in the cwd would be imported, against the repo's `-P` convention for spawned Python.
Note: Two-line fix, so the cost tier is high but the threat is low. Batch both spawns in one PR.

## super-fr#1279: fr-acceptance-nag.sh claims `fr acceptance status` is gate-exempt; it is not
Still live: the comment at `hooks/fr-acceptance-nag.sh:74-75` (was 24-25) says `fr acceptance status` is exempt from the migration gate. `acceptance` is not in `READ_ONLY_COMMANDS` (`artifacts/trigger.py:91`ff), and the hook's own stale-artifacts branch shows the gate does run.
Note: Comment-only fix. Bundle with super-fr#1429.

## super-fr#1259: Resumed Claude Code session keeps a stale FR_HARNESS_FR pin after an fr upgrade
Still live. `plugins/super-fr/hooks/fr-binary-pin.sh:27` only appends to `$CLAUDE_ENV_FILE` and never strips stale sibling `sessionstart-hook-*.sh` pins. `packages/fr/src/fr/binary_identity.py:90-91` still tells the user to `restart the session to re-pin it`, which a resume cannot do. Only a warning, but on every call.

## Why these belong together
Tier 2: the edit gate silently off after archiving the last plan; relative PATH and cwd trusted by hooks and spawned python. Guard change: needs an independent adversarial review before merge.

## Delivery rules
- Work on branch `feat/batch-guard-trust`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1277
  Closes derio-net/super-fr#1429
  Closes derio-net/super-fr#1230
  Closes derio-net/super-fr#1279
  Closes derio-net/super-fr#1259
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

Never add the `approved-fr` label: it is the operator's approval to merge, and fr voids it on your next push.

<!-- fr:journal kind=decision scope=spec id=d1-durable-opt-in created=2026-11-15T16:55:37+00:00 decided_by=operator -->
### d1-durable-opt-in · decision · #1277: archive keeps plans/.gitkeep AND gates accept docs/superpowers/implemented/plans/

Operator chose both fixes (recommended). Rule text, repo mirror, override rules and AGENTS.md updated to match. Spec R1, R2.

<!-- fr:journal kind=decision scope=spec id=d2-resolve-scope created=2026-11-15T16:55:37+00:00 decided_by=operator -->
### d2-resolve-scope · decision · #1429: both git resolvers plus every bare fr spawn in hooks and the OpenCode plugin

Operator chose resolvers + all fr spawns (recommended) over named-sites-only or also routing every bare git call in hook scripts (non-goal). Spec R3, R4.

<!-- fr:journal kind=decision scope=spec id=d3-pin-resume created=2026-11-15T16:55:37+00:00 decided_by=operator -->
### d3-pin-resume · decision · #1259: strip sibling pins in fr-binary-pin.sh and reword the warning to resume or restart

Operator chose strip siblings + reword (recommended); the same-package-dir warning stays. Spec R7, R8.

<!-- fr:journal kind=decision scope=spec id=d4-verification created=2026-11-15T16:55:37+00:00 decided_by=operator -->
### d4-verification · decision · Verification: strategy candidate, gate developer; rows proven by CI tests

Operator chose candidate + developer (recommended). Each row is `none` with CI tests named; the walk runs the candidate smoke. No Test Plan (no post-merge row).

<!-- fr:journal kind=decision scope=spec id=d5-adversarial-review created=2026-11-15T16:55:37+00:00 decided_by=operator -->
### d5-adversarial-review · decision · The security lens in-run is the independent adversarial review for this guard change

Operator chose the security lens (recommended), briefed adversarially - try to make a gate fail open or to run a planted binary or module.

<!-- fr:journal kind=decision scope=spec id=d6-python-flag created=2026-11-15T16:55:37+00:00 decided_by=operator -->
### d6-python-flag · decision · #1230 uses -P (repo convention), settled by the code, not asked

Every fr-spawned Python runs with -P (AGENTS.md fr/ops paragraph). -P drops the cwd from sys.path for -c while keeping site packages.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-15T16:55:37+00:00 lens=security step=brainstorm -->
### lens-security-1 · lens · Guard change - try to make a gate fail open or run a planted git, fr or Python module

<!-- fr:journal kind=finding scope=spec id=f1 created=2026-11-15T17:04:16+00:00 state=open review_scope=in -->
### f1 · finding [open] (reviewer: in scope) · R2's new literal path fails the fr-paths-fallback tripwire unless it is pinned

tests/unit/test_tripwire_artifact_paths.py:426-451 FALLBACK_LINES; fr-isolation-decision.sh:332; marker.ts:273. Spec must mark both new lines and add them to FALLBACK_LINES.

<!-- fr:journal kind=finding scope=spec id=f2 created=2026-11-15T17:04:16+00:00 state=open review_scope=in -->
### f2 · finding [open] (reviewer: in scope) · Docs pages that cover the changed paths are not named; one states the old fr-enabled test

docs/explainers/fr-isolation.md:129-130, docs/cloud-setup.md:118, docs/herdr-control-sessions.md, docs/reference/install.md, packages/fr/src/fr/harness/parity.yaml:114.

<!-- fr:journal kind=finding scope=spec id=f3 created=2026-11-15T17:04:16+00:00 state=open review_scope=in -->
### f3 · finding [open] (reviewer: in scope) · Hook inventory misses fr-worktree-create.sh:129/:139 and misdescribes the existing command -v fr guards

fr-worktree-create.sh:129,139; fr-session-bind.sh:23; fr-session-unbind.sh:28; fr-worktree-remove.sh:23.

<!-- fr:journal kind=finding scope=spec id=f4 created=2026-11-15T17:04:16+00:00 state=open review_scope=in -->
### f4 · finding [open] (reviewer: in scope) · Row hooks-trust-absolute-path-only claims more than the non-goals allow

Bare git in hook scripts stays (d2); the row must be narrowed to the resolvers and the fr-starting sites.

<!-- fr:journal kind=finding scope=spec id=f5 created=2026-11-15T17:04:16+00:00 state=open review_scope=in -->
### f5 · finding [open] (reviewer: in scope) · Archive design names a non-existent staged-paths record and the wrong live root

archive.py:408-418 MoveLog holds moves only; use kind_dir('plan', space_for(repo_root)); state quiet/stealth behaviour.

<!-- fr:journal kind=finding scope=spec id=f6 created=2026-11-15T17:04:16+00:00 state=open review_scope=in -->
### f6 · finding [open] (reviewer: in scope) · The .gitkeep write would follow a repo-planted symlink

Use lstat + O_CREAT|O_EXCL|O_NOFOLLOW; test the symlink case.

<!-- fr:journal kind=finding scope=spec id=f7 created=2026-11-15T17:04:16+00:00 state=open review_scope=in -->
### f7 · finding [open] (reviewer: in scope) · The sibling-pin rewrite can race other SessionStart hooks; temp file unspecified

Read-then-mv drops a concurrent append by another plugin's hook now at that position; record the Claude Code layout as an assumption.

<!-- fr:journal kind=finding scope=spec id=f8 created=2026-11-15T17:04:16+00:00 state=open review_scope=in -->
### f8 · finding [open] (reviewer: in scope) · Row gate-survives-last-plan-archive does not isolate R2 from R1

Fixture must have implemented/plans/<x>, no plans dir, no profile.

<!-- fr:journal kind=finding scope=spec id=f9 created=2026-11-15T17:04:16+00:00 state=open review_scope=out -->
### f9 · finding [open] (reviewer: out of scope) · Other bare-name spawns remain (bash, gh in the plugin; jq in hooks)

tui/segment.ts:47, push.ts:35, command -v jq in hooks. Same class as #1429 but outside d2's scope.

<!-- fr:journal kind=finding scope=spec id=f10 created=2026-11-15T17:04:16+00:00 state=open review_scope=out -->
### f10 · finding [open] (reviewer: out of scope) · The legacy archive dir is not an fr-enabled signal

paths.py:71 plan-legacy-archived; fr migrate moves that layout.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-15T17:04:16+00:00 -->
### spec-review-1 · review · independent spec review: 10 findings (8 in scope f1-f8; 2 out f9, f10)

Decisions d1-d6 honoured; Verification grammar parses (spec_section.py:39-46); every cited file:line verified; -P valid (requires-python >=3.11).

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-15T17:04:16+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · R2 must be proven without R1's .gitkeep, and relative-PATH tests must cover every listed hook and module

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-15T17:04:16+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · Every new resolve or append path must stay fail-open and never turn a failed resolve into a non-zero hook exit

<!-- fr:journal kind=finding scope=spec id=f1-resolved created=2026-11-15T17:04:16+00:00 state=fixed resolves=f1 -->
### f1-resolved · finding [fixed] · resolves f1: R2's new literal path fails the fr-paths-fallback tripwire unless it is pinned

Design A: both new lines carry # fr-paths-fallback and are added to FALLBACK_LINES.

<!-- fr:journal kind=finding scope=spec id=f2-resolved created=2026-11-15T17:04:16+00:00 state=fixed resolves=f2 -->
### f2-resolved · finding [fixed] · resolves f2: Docs pages that cover the changed paths are not named; one states the old fr-enabled test

Design A Text names the explainer, parity.yaml and the fr docs check pages; Design E updates docs/cloud-setup.md.

<!-- fr:journal kind=finding scope=spec id=f3-resolved created=2026-11-15T17:04:16+00:00 state=fixed resolves=f3 -->
### f3-resolved · finding [fixed] · resolves f3: Hook inventory misses fr-worktree-create.sh:129/:139 and misdescribes the existing command -v fr guards

Background lists every site incl. worktree-create :129/:139 and which hooks source the lib; Design B states each hook's fail-open fallback.

<!-- fr:journal kind=finding scope=spec id=f4-resolved created=2026-11-15T17:04:16+00:00 state=fixed resolves=f4 -->
### f4-resolved · finding [fixed] · resolves f4: Row hooks-trust-absolute-path-only claims more than the non-goals allow

Row narrowed (amendment below) to the resolvers and fr-starting hooks/modules.

<!-- fr:journal kind=finding scope=spec id=f5-resolved created=2026-11-15T17:04:16+00:00 state=fixed resolves=f5 -->
### f5-resolved · finding [fixed] · resolves f5: Archive design names a non-existent staged-paths record and the wrong live root

Design A: live root is kind_dir('plan', space_for(repo_root)); only git add, MoveLog unchanged; quiet/stealth stated.

<!-- fr:journal kind=finding scope=spec id=f6-resolved created=2026-11-15T17:04:16+00:00 state=fixed resolves=f6 -->
### f6-resolved · finding [fixed] · resolves f6: The .gitkeep write would follow a repo-planted symlink

Design A: lstat check plus O_CREAT|O_EXCL|O_NOFOLLOW; Verification row tests the symlink case.

<!-- fr:journal kind=finding scope=spec id=f7-resolved created=2026-11-15T17:04:16+00:00 state=fixed resolves=f7 -->
### f7-resolved · finding [fixed] · resolves f7: The sibling-pin rewrite can race other SessionStart hooks; temp file unspecified

Design E rewritten append-only (no rewrite, no delete, no temp file), so a concurrent append cannot be lost; Claude Code layout recorded as an observed assumption; R7 reworded.

<!-- fr:journal kind=finding scope=spec id=f8-resolved created=2026-11-15T17:04:16+00:00 state=fixed resolves=f8 -->
### f8-resolved · finding [fixed] · resolves f8: Row gate-survives-last-plan-archive does not isolate R2 from R1

Verification row pins the fixture: implemented/plans/<x>, no plans dir, no profile.

<!-- fr:journal kind=finding scope=spec id=f9-resolved created=2026-11-15T17:04:16+00:00 state=open resolves=f9 out_of_scope=true -->
### f9-resolved · finding [out-of-scope] · resolves f9: Other bare-name spawns remain (bash, gh in the plugin; jq in hooks)

Pre-existing bare spawns of bash/gh/jq; not touched by this change; listed in Non-goals, filed at deliver.

<!-- fr:journal kind=finding scope=spec id=f10-resolved created=2026-11-15T17:04:16+00:00 state=open resolves=f10 out_of_scope=true -->
### f10-resolved · finding [out-of-scope] · resolves f10: The legacy archive dir is not an fr-enabled signal

Pre-existing legacy layout; this change does not create it; listed in Non-goals.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-15T17:04:18+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  archive-keeps-live-plans-root: none
  gate-survives-last-plan-archive: none
  hooks-trust-absolute-path-only: none
  lock-probe-ignores-cwd: none
  resume-repins-fr-binary: none
row_kinds:
  archive-keeps-live-plans-root: none
  gate-survives-last-plan-archive: none
  hooks-trust-absolute-path-only: none
  lock-probe-ignores-cwd: none
  resume-repins-fr-binary: none
run_gate: developer
run_kind: candidate
```
