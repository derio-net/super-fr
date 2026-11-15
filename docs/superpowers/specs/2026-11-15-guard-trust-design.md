# Guards that switch off or trust the wrong binary — design

Batch `guard-trust`: super-fr#1277, #1429, #1230, #1279, #1259, delivered as one PR on
`feat/batch-guard-trust`.

## Background

Five defects share one shape. A guard either quietly stops guarding, or trusts a file
that something other than the operator put in its path.

- **#1277.** The edit gate decides that a repo is fr-enabled with a bare directory test:
  a `.devcontainer/*/devcontainer.json`, or a `docs/superpowers/plans` directory
  (`plugins/super-fr/hooks/lib/fr-isolation-decision.sh:332` `_fr_is_enabled`, used by
  Claude Code and Hermes; `packages/fr-opencode-plugin/src/marker.ts:273` `frEnabled`).
  `fr archive` moves the last live plan out with `git mv`
  (`packages/fr/src/fr/archive.py:460` `archive_plan_dir`) and leaves nothing behind. Git
  tracks no empty directory, so a fresh clone of a repo with no devcontainer profile has no
  `docs/superpowers/plans`, reads as not fr-enabled, and the gate allows base-clone edits
  without a word. super-fr escapes only because it commits `docs/superpowers/plans/.gitkeep`.
- **#1429.** `fr_fr_resolve` / `resolveFr` already trust only absolute PATH entries and
  start the exact file they checked (a relative entry such as `.`, `bin` or an empty one
  names a file in whatever directory the hook runs from, possibly one planted in the repo
  being edited). Two lookups still do not:
  - git: `fr_git_resolve` (`fr-isolation-decision.sh:152-171`) uses `command -v` for a bare
    candidate, and the default `FR_GIT_CANDIDATES` starts with the bare `git`;
    `git.ts` `onPath` (`packages/fr-opencode-plugin/src/git.ts:55-62`) accepts any non-empty
    entry, relative ones included.
  - fr by bare name: `hooks/fr-worktree-create.sh:59-60`, `fr-binary-pin.sh:19-21`,
    `fr-session-bind.sh:69-74`, `fr-session-unbind.sh:35`, `fr-worktree-remove.sh:39`,
    `fr-run-idle-guard.sh:83`; and in the plugin `pin.ts:39`, `claim.ts:65`, `bind.ts:96`,
    `idle.ts:110`, each `run("fr", …)` through `spawn.ts`, which does no resolution.
- **#1230.** `packages/fr/src/fr/file_lock.py:31-37` and
  `packages/fr-herdr/src/fr_herdr/managed.py:134-142` run `sys.executable -c 'import fcntl…'`
  without `-P`. For `-c`, `sys.path[0]` is the inherited cwd, so a `fcntl.py` there is
  imported first. The repo's convention is `-P` on every Python it spawns.
- **#1279.** The comment at `hooks/fr-acceptance-nag.sh:74-75` says `fr acceptance status`
  is exempt from the artifact-migration gate. It is not: `acceptance` is not in
  `fr.artifacts.trigger.READ_ONLY_COMMANDS`, and the hook's own stale-artifacts branch
  (lines 85-88) exists because the gate does run.
- **#1259.** `fr-binary-pin.sh` appends `export FR_HARNESS_FR=…` to `$CLAUDE_ENV_FILE`.
  Claude Code gives each SessionStart hook position its own file,
  `<session-env dir>/sessionstart-hook-<N>.sh`, and a resume can run the hook at a different
  position from the original start. The old file stays and can be sourced last, so a resumed
  session keeps the old pin. `binary_identity.judge` (`packages/fr/src/fr/binary_identity.py:83-94`)
  then warns on every `fr` call: "restart the session to re-pin it", which a resume (the
  restart the operator just did) does not do.

## Requirements

R1. When `fr archive` moves the last plan folder out of `docs/superpowers/plans/`, it writes `docs/superpowers/plans/.gitkeep` and stages it in the same archive, so the live plans root exists in every fresh clone.
R2. The edit gate on every harness (the bash decision library behind Claude Code and Hermes, and the OpenCode plugin) also treats a repo as fr-enabled when `docs/superpowers/implemented/plans/` exists; every existing fr-enabled check is kept. The shipped rules, the repo mirror rule and AGENTS.md state the new test.
R3. The git resolvers (`fr_git_resolve` in the bash library, `resolveGit` in the OpenCode plugin) resolve a bare candidate name only through absolute PATH entries, to an executable regular file, and run exactly that path; an absolute candidate is unchanged.
R4. Every Claude Code hook and OpenCode plugin module that starts `fr` starts the absolute path `fr_fr_resolve` / `resolveFr` returns, never a bare name; when no trusted `fr` resolves, it does what it does today when `fr` is missing.
R5. The lock probes in `fr/file_lock.py` and `fr_herdr/managed.py` start Python with `-P`, so a module in the inherited cwd is never imported.
R6. `fr-acceptance-nag.sh` no longer claims that `fr acceptance status` is exempt from the artifact-migration gate.
R7. `fr-binary-pin.sh` removes every `export FR_HARNESS_FR=` line from the `sessionstart-hook-*.sh` files in its env file's directory before it writes its own, so after a start or a resume the session holds exactly one pin, the newest.
R8. When the pin names the running package directory at another version, the warning tells the operator to resume or restart the session to re-pin it.

## Design

### A. Durable opt-in (R1, R2) — #1277

**Archive.** `archive_plan_dir` (`fr/archive.py`), after its `git mv`, checks the live root
(`KIND_DIRS` for the active plan dir). When no entry other than `.gitkeep` is left, it writes
an empty `.gitkeep` there if missing and `git add`s it. The write is recorded with the other
staged paths, so a caller that stages or reports the archive's changes sees it. One archive
can move several plans; only the move that leaves the root empty writes the file, and writing
an existing `.gitkeep` is a no-op.

**Gate.** `_fr_is_enabled` gains one line after the plans test:
`[ -d "$1/docs/superpowers/implemented/plans" ] && return 0`. `frEnabled` in `marker.ts` gains
the same `isDir` test. Both stay filesystem-only (no subprocess on the edit path). A repo that
archived its last plan before this fix, and has no `.gitkeep`, still has
`implemented/plans/`, so it is gated again on the next hook run with nothing to migrate. The
fr-isolation-guard's cross-repo check reads the same library function, so it follows.

**Text.** `plugins/super-fr/rules/fr-isolation-required.md` ("A repo is fr-enabled when…"),
the repo mirror `.claude/rules/fr-isolation-required.md` (hand-maintained), the two override
rules that restate the test (`fr-worktree-override.md`, `fr-plan-override.md`), and AGENTS.md's
"Either alone qualifies it" paragraph name the archive directory as a third qualifier. Then
`scripts/sync-opencode.py` and `scripts/sync-hermes.py` regenerate the mirrors.

### B. Absolute PATH entries only (R3, R4) — #1429

**git, bash.** In `fr_git_resolve`, a non-absolute candidate is looked up the way
`fr_fr_resolve` looks up `fr`: walk `PATH`, skip every entry that does not start with `/`, and
take the first `<dir>/<name>` that is a regular file and executable. `command -v` goes. The
default candidate list stays as it is.

**git, OpenCode.** `onPath` in `git.ts` skips an entry that is empty or not `isAbsolute`, and
requires a regular file (`statSync().isFile()`) as `fr.ts`'s `executableFile` does; the
resolved path is the one spawned. The cache key is unchanged.

**fr, hooks.** Each hook that starts `fr` sources `lib/fr-isolation-decision.sh` (where it does
not already), calls `fr_fr_resolve`, and runs `"$FR_FR_BIN"`. Where the hook today guards with
`command -v fr` and skips, a failed resolve skips the same way. Where it calls `fr` unguarded
and ignores the failure (`fr-session-bind.sh`, `fr-session-unbind.sh`), a failed resolve
skips the call. `fr-worktree-remove.sh` falls back to its existing failure path. Inside
`fr-run-idle-guard.sh` the background `exec fr` becomes `exec "$FR_FR_BIN"`. The pin hook
resolves the same way, so the identity it pins is the identity of the `fr` the hooks run.

**fr, OpenCode.** `pin.ts`, `claim.ts`, `bind.ts` and `idle.ts` call `resolveFr()` at call
time and spawn its result. A `null` result is treated as a failed spawn (pin nothing, claim
nothing, bind nothing, no idle verdict), which is each module's current answer when `fr` is
missing. `spawn.ts` stays a transport.

### C. Spawned Python ignores the cwd (R5) — #1230

Both probes become `[sys.executable, "-P", "-c", …]`. `-P` (Python 3.11+, the workspace
floor) drops the implicit cwd entry from `sys.path` and keeps the environment's site
packages, matching the `python -m fr` convention.

### D. Nag comment (R6) — #1279

Rewrite the comment above the capture: `fr acceptance status` runs behind the migration gate,
which can migrate and commit or refuse on the way in; stderr is captured so both outcomes are
relayed rather than swallowed.

### E. One pin per session (R7, R8) — #1259

Before appending, `fr-binary-pin.sh` walks `"$(dirname "$CLAUDE_ENV_FILE")"/sessionstart-hook-*.sh`
(its own file included). For each regular file that is not a symlink and contains a line
starting `export FR_HARNESS_FR=`, it writes the file without those lines to a temporary file in
the same directory and `mv`s it over the original. Other lines and other files are untouched.
Then it appends its pin as now. Every step stays fail-open: a file it cannot rewrite is left as
it is, and the hook still exits 0. The hook runs before the session env is sourced, so the
removal takes effect on the same start or resume.

`judge` keeps the same-package-dir `warn` and the cloud silence. The message becomes
`fr: this fr was upgraded to <new> after the session pinned <old>; resume or restart the
session to re-pin it.`

## Verification

strategy: candidate
gate: developer

- archive-keeps-live-plans-root: none — CI test: archive the only plan of a fixture repo, clone it fresh, and check `docs/superpowers/plans/.gitkeep` is tracked
- gate-survives-last-plan-archive: none — CI tests: a fresh clone of a fixture whose only plan was archived is denied a base-clone edit by the bash library (Claude Code and Hermes entrypoints) and by the OpenCode plugin's `frEnabled`
- hooks-trust-absolute-path-only: none — CI tests: with a planted `git` or `fr` behind a relative PATH entry, neither git resolver nor any `fr`-starting hook or plugin module runs it (bash tests and `bun test`)
- lock-probe-ignores-cwd: none — CI test: a planted `fcntl.py` in the cwd is not imported by either probe
- resume-repins-fr-binary: none — CI tests: a session-env dir holding a stale sibling pin keeps only the new one after the hook runs; `judge`'s message names resume

The walk runs the candidate smoke only (install, version, status in a fresh fixture).

## Acceptance rows

| Row | Requirement | Claim |
|---|---|---|
| `archive-keeps-live-plans-root` | R1 | Archiving the last plan leaves a tracked `docs/superpowers/plans/.gitkeep`. |
| `gate-survives-last-plan-archive` | R2 | A repo that archived its last plan stays fr-enabled on every harness and in every fresh clone. |
| `hooks-trust-absolute-path-only` | R3, R4 | A `git` or `fr` reachable only through a relative PATH entry is never run by a hook or the OpenCode plugin. |
| `lock-probe-ignores-cwd` | R5 | The lock probes never import a module from their cwd. |
| `resume-repins-fr-binary` | R7, R8 | A resumed Claude Code session is pinned to the `fr` installed at resume, and the upgrade warning gives advice that works. |

R6 is a comment correction with no product behaviour, so it has no row.

## Non-goals

- Routing the other bare `git` calls inside the hook scripts (isolation guard, worktree
  create/remove, nag, sentinel) through the resolved git. The operator kept them out of this
  batch.
- A durable opt-in marker beyond the archive directory (for example `.fr/` or
  `docs/superpowers/` as a whole).
- Silencing the same-package-dir warning.
