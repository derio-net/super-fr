---
name: fr-isolation
description: >
  Run work in an isolated workspace: git worktree + devcontainer, driven through
  the `fr isolation` CLI (exec-bridge). Use when feature work must not touch the
  base repo, when fr-brainstorming or fr-goal needs a workspace, when the operator
  says "isolate this" / "run it in the container", or to clean up after a merged
  PR. devcontainer mode needs a profile; host/external modes are docker-less.
---

# fr-isolation

A workspace contract, not just a worktree: a git worktree OUTSIDE the repo (`~/.cache/fr/worktrees/<main-checkout>/<branch>`),
commands in the profile's devcontainer, base repo untouched while the run is live. Plain shell, any agent or human.

**Announce at start:** "I'm using fr-isolation to run this work isolated."

## Hard requirements

- Inside a git repo. **devcontainer mode** (default) needs ≥1 profile (`.devcontainer/<profile>/devcontainer.json`); missing →
  exit 2 pointing at fr-init. NEVER proceed unisolated; offer the fr-init interview (pause, resume).
- **host-worktree** mode (`FR_ISOLATION_TARGET=worktree`, same contract, docker-less): fr worktree, the host process env as-is — NO
  profile, no secrets provisioning. A host-level declaration, never a per-call flag.
- **external** mode (valid preparer-written `.fr-isolation` marker, `mode:external`): fr adopts the container's checkout — `up --branch`
  ensures the branch in place; restart/stats refuse, gc reports (the container's owner runs both).
- Any other `FR_ISOLATION_TARGET` value fails closed naming `devcontainer|worktree`.

## Lifecycle

```bash
fr isolation up --branch <b> [--profile <name>] [--session <id>] [--print-path]  # worktree + container; --print-path: last stdout line = path
fr isolation exec --branch <b> -- CMD ...                                         # every build/test/run; resumes a stopped container
fr isolation status [--branch ...] [--session <id>] [--format json] [--stats] [--push-check]  # state + bound sessions
fr isolation attach|detach --session <id> [--repo <path>] [--branch ...]         # bind/unbind a harness session
fr isolation restart [--branch ...] [--force]                                     # bounce a wedged container, worktree kept
fr isolation stop [--branch ...]                                                  # free a container's resources; everything else kept
fr isolation rebuild [--branch ...] [--no-cache]                                  # recreate the container from the (changed) profile
fr isolation down --branch <b> | --worktree <path> | --all [--dry-run] [--yes] [--force] [--no-preserve]  # teardown; --all lists blast radius first
fr isolation gc [--repo <path>] [--dry-run] [--format json]                       # reconcile fr-owned workspaces, ALL three modes
```

- `up` (devcontainer mode) resolves the profile (flag → repo default from `.devcontainer/fr-profiles.yaml` → sole profile), creates the
  worktree under the MAIN checkout's name (even from inside another worktree), ensures the host secrets env-file, starts the container
  with the base repo's `.git` mounted at the same absolute path. Re-running `up` on a live workspace keeps its record and sessions.
- **Container vs worktree** (the container is disposable, the worktree is the work): a changed profile: `rebuild`; a different
  profile: `down` + `up --profile`, and the run record is preserved across it.

| Situation | Verb | Worktree, uncommitted files, run record | In-container installs |
|---|---|---|---|
| wedged container | `restart` | kept | kept |
| pause the work, free RAM/CPU | `stop`; the next `exec` resumes it (stderr notice) | kept | kept |
| profile changed (feature, image, env) | `rebuild` (`--no-cache` for a clean image) | kept | lost (container recreated) |
| different profile, or the work is done | `down` (+ `up --profile <p>`) | worktree removed; fr's uncommitted records preserved | lost |

- **Branch base (#322, #438):** a local `<B>` is reused (behind/diverged from `origin/<B>` → `WARNING`, never rebased); else an existing
  `origin/<B>` is fetched and checked out (`--base` beside it is refused); else a NEW branch is cut from freshly-fetched `origin/<default>`,
  never HEAD. `--base <ref>` = verbatim, no fetch; `--no-fetch` = LOCAL refs. No remote/fetch/ref → local HEAD + `WARNING`, never aborts.

## Exec-bridge discipline

- EVERY build/test/lint/run command goes through `fr isolation exec -- ...`; file
  edits happen in the worktree directly (host-visible), execution in-container.
- Credential boundary (devcontainer mode): the container sees only the profile's
  env-file (`~/.config/fr/secrets/<repo>/<profile>.env`), NO SSH identity (#377).
  ALL git-host I/O (push/fetch, PR/MR creation, `gh`/`glab`/`tea` reads in
  `status`/`down`/`gc`) runs on the HOST outside `exec`; `status --push-check` previews.
- Pre-push guard (#320): a push to a branch whose PR is `MERGED`/`CLOSED` is
  denied by `fr-merged-pr-push-guard.sh` — cherry-pick onto `main` or a fresh PR.
- The harness resets cwd to base each call, so host-side git/gh is compound `cd
  <worktree> && …`; the guard allows a leading `cd` under `~/.cache/fr/worktrees`
  / temp (#279); `/add-dir` (#281) persists a bare `cd`. Never run base commands.
- `up` writes a gitignored `.fr-isolation` marker (`mode` records the mode) that
  the `fr-isolation-required` PreToolUse hook reads to ALLOW edits; tracked files
  in an fr-enabled base clone are blocked (`FR_BASE_OK=1` / `.fr-isolation-allow`
  escape). `down` removes it. See that rule (#328).

## Session bindings (traceability)

Which harness session holds which workspace — traceability only; the edit gate never reads a binding. `attach` records
`{session_id, harness, attached_at}` in the workspace state (source of truth) plus a derived index `~/.cache/fr/sessions/<id>.json`
(`FR_SESSIONS_DIR`; keys `session_id, harness, repo_root, branch, worktree, profile, attached_at`), one binding per session.
`up --session` binds in the same call; `down` detaches everyone AFTER a successful teardown (a refused `down` keeps bindings);
`gc` prunes stale indexes. Claude transports (plugin hooks, always exit 0): `fr-session-bind.sh` (PostToolUse Bash; parses
`fr isolation up|exec|down …`, leading `cd` folded), `fr-session-unbind.sh` (SessionEnd), `fr-worktree-create.sh` (`claude --worktree` /
`EnterWorktree` → `up --session --print-path`, branch `wt/<name>`; `agent-*` keep Claude's default `<repo>/.claude/worktrees/`
shape), `fr-worktree-remove.sh` (`down --worktree`; a refusal keeps the workspace). Hermes has no bind transport yet.

**Status line** (spec 2026-09-14): `scripts/fr-statusline-segment.sh` answers "which branch, and is this session in fr-isolation?" —
shell+jq+git, never fr. Input: status-line JSON on stdin, or `--cwd <dir>` (no stdin). A live binding wins; else the cwd's branch, `fr`
when the cwd's toplevel is an fr workspace. `--format plain` (state `fr`/`none`, `branch: <b>`/ `no branch`, `worktree: <path>`/`no
fr-isolation`), `ansi` (the two rows, green when fr, purple when not), `oneline` (`fr:<branch>`/`<branch>`, 40-char slot). The v1 `iso:`
hint and worktree gauge are gone. **Claude Code:** set `statusLine.command` to `bash
~/.claude/plugins/cache/derio-net--super-fr/super-fr/current/scripts/fr-statusline-claude.sh`, symlink it (`ln -s <that path>
~/.claude/statusline.sh`; the script finds the segment next to its real file), or in your own script: `rows=$(printf '%s' "$data" | bash
<scripts>/fr-statusline-segment.sh --format ansi)`, line 2 = row 1 + ` | ~/cwd`, line 3 = row 2. **Hermes:** pending
NousResearch/hermes-agent#109596 — `display.status_bar.fields: [..., custom]`, `custom_command: "bash <super-fr
checkout>/plugins/super-fr/scripts/fr-statusline-segment.sh --format oneline --cwd ."` (`fr hermes install` copies hooks only, not
scripts). **OpenCode:** no status-line hook (anomalyco/opencode#37464); run `--format oneline --cwd <dir>` from a tmux/herdr status bar.

## Cleanup contract — worktree + container PERSIST after PR creation (back-loaded manual phases push there)

- **gc auto-reconciles merged work, in every mode.** Fires detached on every `up`/`down` (host-wide, no daemon, ≤1 stale): tears down
  MERGED-PR and content-merged workspaces, retires state records whose worktree is gone, removes empty repo folders + stale session indexes,
  and (devcontainer only) reaps orphaned containers / `vsc-*` images. Open-PR, dirty, no-PR work: never touched. **external** only reports.
- **Ownership boundary.** gc acts only where fr ownership is provable (state record, worktree cache, devcontainer label).
- **`down` is the immediate lever** — verifies container + worktree are gone before dropping state (never leaked), and refuses three
  things: an open PR, a dirty worktree (#435), content not on `origin/<default>` (#467).
- **`--force` is operator-requested-and-informed only.** It bypasses all three. An agent must never reach for it on its own initiative —
  only after the operator asks — and must first name what would be destroyed: `git worktree remove --force` drops the worktree and fr's
  record; the branch and its commits stay in the repo; uncommitted changes do not — except fr's own records under `docs/superpowers/`
  (a run cursor, journals), which are preserved and restored by the next `up --branch`; `--no-preserve` discards them too. A refusal
  names the active run it would end. **Prose with no tripwire** — nothing can test "an agent decided by itself" — said plainly.

## Recovery (#341) and failure handling

- **Wedged or broken container:** `restart [--force]` (installs kept), then `rebuild` (worktree kept) — never `down --force` + `up`.
- **Orphaned pipeline sentinel** (base commands denied, no workspace to `cd` into): the guard heals **per sentinel** — once EVERY workspace
  the session bound is gone it retires that one and fails open (#472); unbound (fresh/legacy) stays armed (#529). `down --all` is repo-wide: `--dry-run` first; another session's workspace needs `--yes`.
- `devcontainer up` failures surface verbatim — missing Docker, a broken profile, an absent secrets file are operator-environment issues:
  report and stop, never work around isolation (no silent degradation to a weaker mode).
