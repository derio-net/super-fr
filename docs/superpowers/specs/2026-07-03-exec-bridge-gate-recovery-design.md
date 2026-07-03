# Spec — exec-bridge gate: recovery deadlocks (umbrella #341, Tasks 2 & 3)

**Issue:** [#341](https://github.com/derio-net/super-fr/issues/341) — umbrella over
#299 (Task 1, **already shipped** via #305/#306), #329 (Task 2), #307 (Task 3).

**Scope (operator Q&A, 2026-07-03):** Tasks 2 & 3 only. Task 1's fixes (gate
`fr init` allowlist, `exec`/`status` single-workspace branch resolution, scaffold
commits-by-default) are verified present in the current tree — no new code.

Pure CLI + bash-hook code; nothing deploys → **no post-merge Test Plan**.

---

## Task 2 — orphaned session sentinel deadlocks all host ops (#329)

### Mechanism (recap)

`fr-pipeline-sentinel.sh` (PostToolUse[Skill]) writes a session-keyed sentinel
(`$FR_SENTINEL_DIR/<session>.json`, default `~/.cache/fr/sentinels/`) naming the
base repo when fr-goal / fr-brainstorming / fr-execute runs.
`fr-isolation-guard.sh` (PreToolUse[Bash]) then denies **every** base-repo-cwd
Bash command except `fr isolation …` / the bootstrap allowlist, telling the
agent to `cd <worktree> && …`. When all worktrees are torn down but the sentinel
survives (observed live derio-net/frank 2026-06-21, fr-goal close-out after two
merged PRs), the `cd <worktree>` escape is unsatisfiable and every `git` / `gh` /
`kubectl` / `cat` is denied with no in-CLI way out.

### 2A — self-heal + explicit escape (Q&A: "self-heal + explicit escape")

**Guard self-heal (`fr-isolation-guard.sh`).** Immediately before the final
`deny`, detect whether any linked git worktree exists for the sentinel's repo:

```
wt=$(git -C "$rroot" worktree list --porcelain 2>/dev/null) \
  && [ "$(printf '%s\n' "$wt" | grep -c '^worktree ')" -eq 1 ] && { rm -f "$sentinel"; exit 0; }
```

- Fires **only** on a *successful* `git worktree list` reporting exactly one
  `worktree ` line (the main checkout, zero linked worktrees). The `cd <worktree>`
  instruction is then unsatisfiable → denying is pure deadlock → **fail open**
  AND remove the orphaned sentinel (self-heal; the next command sees no sentinel
  and exits at the existing "no active pipeline" guard).
- Fails **closed** (falls through to the normal deny) when `git worktree list`
  errors — a non-git cwd or unresolvable repo must not silently un-gate. This is
  what keeps every existing guard test (which use non-git tmp dirs and expect
  `deny`) green.
- Placement: after the `fr isolation` allowlist (line ~91) and the cd-transition
  block, just before the deny `jq` — so `fr …` and worktree-cd commands keep
  their existing allow paths.

**Explicit escape — `fr isolation down --all`.** New `--all` flag on the
existing `down` command:

- Iterates `list_states(root)`; tears down each workspace (`target.down(state,
  force=force)`), honoring the open-PR safety (a workspace with an OPEN PR is
  **kept** unless `--force`, collected and reported, never silently destroyed).
- Then calls a new `clear_repo_sentinels(root)` helper that removes every
  sentinel file whose `repo_root` resolves to this repo (the deliberate "drop
  session state" the issue asks for). The guard self-heal is the backstop; this
  is the eager, explicit lever.
- `--all` ignores `--branch`. Reports: `N torn down, M kept (open PR — rerun with
  --force), K sentinel(s) cleared.`

`clear_repo_sentinels(repo_root)` lives in `fr/isolation/types.py` (with the
other state helpers) and owns the **shared sentinel contract** with the two bash
hooks: `$FR_SENTINEL_DIR` (default `~/.cache/fr/sentinels/`), `<session>.json`
files each `{"repo_root": ...}`. Non-JSON / unreadable files are skipped. Returns
the count removed. A short comment in each bash hook points at this function as
the Python mirror.

### 2B — deny message names its true breadth (Q&A: "keep broad, fix message")

The gate stays broad by design (discipline backstop: *all* base-repo work routes
through the worktree). Only the message is wrong — it says "Host-side git/gh
ops" but the guard gates everything. Rewrite the deny `permissionDecisionReason`
to state the true breadth and name the new escape, e.g.:

> `fr pipeline active — ALL base-repo commands are gated (not just git/gh), so
> work runs in the isolation worktree. Run via `fr isolation exec -- …`, or lead
> with `cd <worktree> && …` to work from the worktree cwd. No worktree left?
> `fr isolation down --all` clears the pipeline. See fr-isolation
> (#265/#279/#329).`

Existing assertions that key on `"fr isolation exec"` and `"cd <worktree> &&"`
stay satisfied; a new assertion checks the message no longer implies git/gh-only
(e.g. contains "ALL" / "not just git/gh") and names `down --all`.

---

## Task 3 — lightweight recovery for a resource-wedged devcontainer (#307)

A `docker run` inside the docker-in-docker daemon thrashed the 4GB container;
even in-container `docker ps` / `ps aux` hung. `fr isolation down` + `up` is a
sledgehammer (drops worktree, node_modules, local DB stack, in-container
installs — 10+ min re-setup) for what should be a container bounce.

### 3A — `fr isolation restart` (Q&A: "restart + status --stats opt-in")

New `restart` command + `Target.restart(state, force=False)`:

- Resolves the container via the existing `_container_id(state)` (docker label
  `devcontainer.local_folder=<worktree>`). No container → `IsolationError`
  ("nothing to restart — run `fr isolation up`").
- Default: `docker restart <id>` (graceful stop→start; the 10s grace then SIGKILL
  is docker's own default). `--force`: `docker restart --time=0 <id>` (immediate
  SIGKILL then start) — for a container too wedged to stop gracefully.
- `docker restart` preserves the container filesystem and the bind-mounted
  worktree; only the process tree is bounced. Non-zero rc → `IsolationError`
  naming the failure and suggesting `--force`.
- Branch resolution mirrors `exec`/`status`: `--branch` omitted → the single
  active workspace, error listing branches if >1.
- Emits `isolation restart: <branch> bounced (<id>).`

### 3B — `fr isolation status --stats` (opt-in)

- New `--stats` flag on `status`. Default status is unchanged (fast: no docker
  stats call).
- With `--stats`, a new `Target.stats(state)` runs `docker stats --no-stream
  --format '{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}' <id>` for each **running**
  container (pipe-delimited — MemUsage contains a space). Returns
  `{"cpu", "mem", "mem_perc"}` or `None` (no container, not running, or command
  failure — so an exited container reads `stats=n/a`, never an error).
- Text row appends `stats=cpu=<c> mem=<m> (<p>)` or `stats=n/a`. JSON rows carry
  a `"stats"` key (object or null). Lets an agent *detect* a thrashing container
  instead of inferring it from hung execs.

---

## Files touched

| File | Change |
|---|---|
| `plugins/super-fr/hooks/fr-isolation-guard.sh` | self-heal fail-open + clear; rewritten deny message |
| `plugins/super-fr/hooks/fr-pipeline-sentinel.sh` | comment pointing at `clear_repo_sentinels` |
| `packages/fr/src/fr/isolation/types.py` | `sentinel_dir()`, `clear_repo_sentinels()` |
| `packages/fr/src/fr/isolation/local.py` | `Target.restart()`, `Target.stats()` |
| `packages/fr/src/fr/isolation/types.py` (Target proto) | `restart`, `stats` signatures |
| `packages/fr/src/fr/commands/isolation_cmd.py` | `down --all`; `restart`; `status --stats` |
| `plugins/super-fr/skills/fr-isolation/SKILL.md` | document new subcommands (≤2 line headroom — compress) |
| `tests/unit/test_hooks_guard.py` | self-heal cases + message assertion |
| `tests/unit/test_isolation_cmd.py`, `test_isolation.py` | `down --all`, `restart`, `stats` |
| version (`pyproject.toml` ×N + manifests) | `3.5.3` → `3.6.0` (minor: new subcommands) via `scripts/bump-version.py` |

## Test matrix (TDD — red first)

**Guard (bash-driven):** real git repo, zero linked worktrees + sentinel →
allow + sentinel removed (self-heal); real git repo WITH a linked worktree +
sentinel → still deny; non-git dir + sentinel → still deny (fail-closed on git
error, guards existing tests); deny message contains "ALL"/"not just git/gh" and
"down --all".

**CLI:** `down --all` tears down all states + clears sentinels (count returned);
`down --all` keeps an OPEN-PR workspace without `--force`, tears it with
`--force`; `clear_repo_sentinels` removes only matching-repo sentinels, skips
foreign + malformed files. `restart` calls `docker restart <id>`; `--force` →
`docker restart --time=0 <id>`; no container → error. `status --stats` includes
parsed stats for a running container, `None`/`n/a` for exited; default status
makes no stats call.

## Non-goals

- Narrowing the gate to git/gh (rejected in Q&A — keep broad).
- Always-on status stats (rejected — opt-in `--stats`).
- Re-opening Task 1 (#299 shipped).
- Changing single `fr isolation down`'s existing sentinel-clear behavior.
