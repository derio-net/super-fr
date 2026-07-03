# exec-bridge gate — recovery deadlocks (umbrella #341, Tasks 2 & 3)

Closes the two remaining tasks of umbrella [#341](https://github.com/derio-net/super-fr/issues/341).
Task 1 (#299, bootstrap deadlock) already shipped via #305/#306 — verified
present in the tree, no new code. Spec:
`docs/superpowers/specs/2026-07-03-exec-bridge-gate-recovery-design.md`.

Both remaining tasks share one surface — the exec-bridge gate
(`fr-isolation-guard.sh` + the session sentinel) and the `fr isolation`
lifecycle CLI — and one class of fix: make the gate self-heal, and put the
recovery levers on the `fr` CLI so the gate never needs a new host-side hole.

## Task 2 — orphaned session sentinel deadlock (#329)

When an fr pipeline's worktrees are all torn down but the session sentinel
survives (seen live on derio-net/frank during an fr-goal close-out), the guard
denies **every** base-repo command and tells the agent to `cd <worktree>` — but
no worktree exists to cd into. Two mechanisms fix it (operator chose "self-heal
+ explicit escape"):

- **Guard self-heal (Phase 1):** before denying, the guard checks
  `git worktree list`. If a *successful* listing shows only the main checkout
  (zero linked worktrees), the `cd <worktree>` escape is unsatisfiable, so the
  guard **fails open and removes the orphaned sentinel** — the next command sees
  no sentinel and passes cleanly. It fails **closed** when `git worktree list`
  errors (a non-git cwd), which is what keeps every existing guard test green.
- **Explicit escape (Phase 2):** `fr isolation down --all` tears down every
  workspace for the repo (keeping any open-PR workspace unless `--force`) and
  then calls `clear_repo_sentinels()` to drop the session sentinel(s) directly —
  the deliberate "end this pipeline" lever, with the guard self-heal as backstop.

Task 2B (same phase): the guard block is broad **by design** (all base-repo work
routes through the worktree), but its deny message wrongly said "git/gh ops."
Phase 1 rewrites the message to name the true breadth and point at the new
`down --all` escape; the gate itself is unchanged.

`clear_repo_sentinels` (in `fr/isolation/types.py`) owns the Python side of the
sentinel contract shared with the two bash hooks: `$FR_SENTINEL_DIR` (default
`~/.cache/fr/sentinels/`), one `<session>.json` per session carrying
`{"repo_root": ...}`.

## Task 3 — lightweight recovery for a wedged devcontainer (#307)

A resource-thrashed container needs a *bounce*, not a full `down`+`up` (which
drops the worktree, node_modules, local DB stack, and in-container installs).

- **`fr isolation restart` (Phase 3):** `docker restart <id>` (graceful);
  `--force` → `docker restart --time=0 <id>` (immediate SIGKILL then start) for a
  container too wedged to stop gracefully. `docker restart` preserves the
  container filesystem and the bind-mounted worktree — only the process tree is
  bounced. Container id comes from the existing `devcontainer.local_folder`
  label lookup; branch resolution mirrors `exec`/`status`.
- **`fr isolation status --stats` (Phase 3):** opt-in flag runs
  `docker stats --no-stream` for each running container so an agent can *detect*
  a thrashing container instead of inferring it from hung execs. Default
  `status` is untouched (no stats call, stays fast); an exited container reads
  `stats=n/a`, never an error.

## Approach

TDD throughout (red → green → optional refactor). Guard changes are exercised by
driving `fr-isolation-guard.sh` with JSON stdin (the existing
`test_hooks_guard.py` harness); CLI/Target changes through the monkeypatched
`runner` seam (no Docker in unit tests). Nothing here deploys, so there is **no
post-merge Test Plan** — verification is the full suite plus `ruff` and
`bump-version.py --check`.

## Phases

1. **Guard hardening** — self-heal fail-open + accurate deny message (Task 2A
   guard-side + 2B). No deps.
2. **CLI escape hatch** — `fr isolation down --all` + `clear_repo_sentinels`
   (Task 2A CLI-side). No deps.
3. **Container recovery** — `fr isolation restart` + `status --stats` (Task 3).
   No deps.
4. **Docs + version bump** — document the new subcommands in the fr-isolation
   SKILL.md (within the 120-line cap) and bump `3.5.3 → 3.6.0`. Depends on 1–3.
