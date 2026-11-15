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
  - fr by bare name: `hooks/fr-worktree-create.sh:59-60` (the gc reaper) and `:129`/`:139`
    (the `command -v fr` test and the `fr isolation up --session` call that runs on every
    session worktree), `fr-binary-pin.sh:19-21`, `fr-session-bind.sh:23,69-74`,
    `fr-session-unbind.sh:28,35`, `fr-worktree-remove.sh:23,39`, `fr-run-idle-guard.sh:83`;
    and in the plugin `pin.ts:39`, `claim.ts:65`, `bind.ts:96`, `idle.ts:110`, each
    `run("fr", …)` through `spawn.ts`, which does no resolution and answers `code: null` when
    the spawn fails. Each hook today tests `command -v fr` and exits 0 (or, in worktree-create,
    falls back to `mimic_default`) when `fr` is missing. Already sourcing
    `lib/fr-isolation-decision.sh`: `fr-acceptance-nag.sh`, `fr-session-bind.sh`,
    `fr-worktree-create.sh`; not yet: `fr-binary-pin.sh`, `fr-session-unbind.sh`,
    `fr-worktree-remove.sh`, `fr-run-idle-guard.sh`.
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
R7. `fr-binary-pin.sh` makes the newest pin the last `export FR_HARNESS_FR=` line of every `sessionstart-hook-*.sh` file in its env file's directory that holds one, and of its own, by appending only, so after a start or a resume the pin in effect is the newest whatever order the files are sourced in.
R8. When the pin names the running package directory at another version, the warning tells the operator to resume or restart the session to re-pin it.

## Design

### A. Durable opt-in (R1, R2) — #1277

**Archive.** `archive_plan_dir` (`fr/archive.py`), after its `git mv`, looks at the live root,
`plan_dir.parent`, and acts only when that equals `kind_dir("plan", space_for(repo_root))`
(the root `archive_cmd` itself reads). When no entry other than `.gitkeep` is left there, and
`.gitkeep` does not exist as any kind of entry (checked with `lstat`, so a committed symlink,
dangling or not, counts as existing and is left alone), it creates the file with
`os.open(…, O_CREAT | O_EXCL | O_NOFOLLOW | O_WRONLY)` and `git add`s it. Nothing else records
it: `MoveLog` stays a list of `git mv` pairs, and archive commits nothing itself (the caller,
such as `fr debt archive-pr`, commits what is staged). An existing `.gitkeep` is left as it is.
Under quiet or stealth placement the live root is in the `fr` worktree or tracking clone, where
the file is harmless and the gate does not need it: those placements are fr-enabled through
`_fr_placement_enabled`.

**Gate.** `_fr_is_enabled` gains one line after the plans test,
`[ -d "$1/docs/superpowers/implemented/plans" ] && return 0  # fr-paths-fallback`, and
`frEnabled` in `marker.ts` gains the same `isDir` test with the same marker comment. Both new
lines are added, word for word, to `FALLBACK_LINES` in
`tests/unit/test_tripwire_artifact_paths.py`, the map that pins every literal
`docs/superpowers/…` path a hook may name. It is a filesystem fallback like the plans test
beside it, and like that one it does not follow the placement. Both stay filesystem-only (no
subprocess on the edit path). A repo that archived its last plan before this fix, and has no
`.gitkeep`, still has `implemented/plans/`, so it is gated again on the next hook run with
nothing to migrate. Everything else that calls the library function follows: the
fr-isolation-guard's cross-repo branch (`fr-isolation-guard.sh:415`) and the Hermes
merged-PR push guard (`hermes/fr-merged-pr-push-guard.sh:76`).

**Text.** These pages and rules name the archive directory as a third qualifier:
`plugins/super-fr/rules/fr-isolation-required.md` ("A repo is fr-enabled when…"), the repo
mirror `.claude/rules/fr-isolation-required.md` (hand-maintained), the two override rules that
restate the test (`fr-worktree-override.md`, `fr-plan-override.md`), AGENTS.md's "Either alone
qualifies it" paragraph, the fr-isolation explainer (`docs/explainers/fr-isolation.md`, which
states the test), and the fr-isolation-required summary in
`packages/fr/src/fr/harness/parity.yaml`. Then `scripts/sync-opencode.py` and
`scripts/sync-hermes.py` regenerate the mirrors. Every other page whose `covers:` matches a
changed path (`fr docs check` names them, e.g. `docs/herdr-control-sessions.md` for
`managed.py` and `docs/reference/install.md` for the plugin sources) gets a content edit when
it states changed behaviour, else a new `reviewed` stamp.

### B. Absolute PATH entries only (R3, R4) — #1429

**git, bash.** In `fr_git_resolve`, a non-absolute candidate is looked up the way
`fr_fr_resolve` looks up `fr`: walk `PATH`, skip every entry that does not start with `/`, and
take the first `<dir>/<name>` that is a regular file and executable. `command -v` goes. The
default candidate list stays as it is.

**git, OpenCode.** `onPath` in `git.ts` skips an entry that is empty or not `isAbsolute`, and
requires a regular file (`statSync().isFile()`) as `fr.ts`'s `executableFile` does; the
resolved path is the one spawned. The cache key is unchanged.

**fr, hooks.** Each hook that starts `fr` sources `lib/fr-isolation-decision.sh` (where it does
not already), calls `fr_fr_resolve`, and runs `"$FR_FR_BIN"`. In every hook,
`fr_fr_resolve || <what the hook does today when fr is missing>` replaces its
`command -v fr` test: bind, unbind, worktree-remove and the pin hook exit 0;
`fr-worktree-create.sh:129` falls back to `mimic_default`; its gc reaper at `:59-60` is
skipped. No hook may turn a failed resolve into a non-zero exit (worktree-create cannot
decline). Inside `fr-run-idle-guard.sh` the background `exec fr` becomes
`exec "$FR_FR_BIN"`. The pin hook resolves the same way, so the identity it pins is the
identity of the `fr` the hooks run.

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

**Assumption (Claude Code internals, not shown anywhere in this repo).** Each SessionStart hook
position gets its own env file, `<session-env dir>/sessionstart-hook-<N>.sh`; a resume can run
fr's hook at a different position, and the old file stays and is sourced as well, in an order
fr does not control. Observed on Claude Code, macOS, 2026-10-31 (super-fr#1259: files `-8` from
the start and `-5` from the resume, the older value winning). The position file of fr's old
pin may by then belong to another plugin's hook, which can be appending to it concurrently.

So the hook never rewrites or deletes a file; it only appends, which cannot lose another
hook's concurrent append. It walks `"$(dirname "$CLAUDE_ENV_FILE")"/sessionstart-hook-*.sh`,
and to each entry that is a regular file, not a symlink, and holds a line starting
`export FR_HARNESS_FR=`, it appends the new pin line; then it appends to its own
`$CLAUDE_ENV_FILE` as now. Each file's last `FR_HARNESS_FR` line is then the new pin,
whichever file is sourced last. A stale line stays in its file, overridden by the line after
it; the cost is one line per resume. No temporary file exists. Every step stays fail-open: a
file it cannot append to is skipped, and the hook still exits 0. The hook runs before the
session env is sourced, so the new pin takes effect on the same start or resume.

`judge` keeps the same-package-dir `warn` and the cloud silence. The message becomes
`fr: this fr was upgraded to <new> after the session pinned <old>; resume or restart the
session to re-pin it.` `docs/cloud-setup.md`, which quotes the old text, is updated with it.

R7 therefore reads "exactly one pin" as "one pin in effect": every sourced file ends on the
newest one.

## Verification

strategy: candidate
gate: developer

- archive-keeps-live-plans-root: none — CI tests: archive the only plan of a fixture repo, clone it fresh, and check `docs/superpowers/plans/.gitkeep` is tracked; a committed `.gitkeep` symlink is neither followed nor replaced
- gate-survives-last-plan-archive: none — CI tests on a fixture with `docs/superpowers/implemented/plans/<x>`, no `docs/superpowers/plans` and no devcontainer profile (so R1's `.gitkeep` cannot be what passes it): a base-clone edit is denied by the bash library (Claude Code and Hermes entrypoints) and by the OpenCode plugin's `frEnabled`
- hooks-trust-absolute-path-only: none — CI tests: with a planted `git` or `fr` behind a relative PATH entry, neither git resolver nor any `fr`-starting hook (each site listed in Background, `fr-worktree-create.sh:139` included) or plugin module runs it, and each still exits as it does when `fr` is missing (bash tests and `bun test`)
- lock-probe-ignores-cwd: none — CI test: a planted `fcntl.py` in the cwd is not imported by either probe
- resume-repins-fr-binary: none — CI tests: a session-env dir holding a stale pin in a sibling file (alone, and beside another hook's lines) ends with the new pin as the last `FR_HARNESS_FR` line of every such file, other lines untouched, symlinks skipped; `judge`'s message names resume

The walk runs the candidate smoke only (install, version, status in a fresh fixture).

## Acceptance rows

| Row | Requirement | Claim |
|---|---|---|
| `archive-keeps-live-plans-root` | R1 | Archiving the last plan leaves a tracked `docs/superpowers/plans/.gitkeep`. |
| `gate-survives-last-plan-archive` | R2 | A repo that archived its last plan stays fr-enabled on every harness and in every fresh clone. |
| `hooks-trust-absolute-path-only` | R3, R4 | Neither git resolver, and no hook or OpenCode plugin module that starts `fr`, runs a binary reached only through a relative PATH entry. |
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
- Other bare-name spawns of the same class: `bash` (`tui/segment.ts:47`) and `gh`
  (`push.ts:35`) in the plugin, `jq` in the hooks. Filed as a follow-up with the bare-git one.
- The legacy archive dir `docs/superpowers/archived-plans/` as an fr-enabled signal: `fr migrate`
  moves that layout.
