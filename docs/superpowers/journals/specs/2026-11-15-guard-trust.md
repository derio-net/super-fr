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
