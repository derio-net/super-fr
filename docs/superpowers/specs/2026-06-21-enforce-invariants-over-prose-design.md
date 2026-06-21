# Enforce invariants over prose — super-fr#328 Tasks 2 & 3

**Issue:** [super-fr#328](https://github.com/derio-net/super-fr/issues/328)
(umbrella). **Date:** 2026-06-21. **Branch:** `feat/enforce-invariants`.

## Background

Issue #328 consolidates three improvements that share one root principle:

> Safety / cost / correctness invariants must be **enforced** (hook, CI gate,
> fail-loud check) — not left to prose, because prose gets bypassed under load.

**Task 1 (merge-race, #320) is already shipped** in v3.4.x and is out of scope:
`plugins/super-fr/hooks/fr-merged-pr-push-guard.sh` (pre-push guard),
`LocalWorktreeDevcontainerTarget.verify_merge` / `branch_changes_present` +
`fr isolation verify-merge` (close-out), and the running fr-goal skill's
draft-PR discipline. Verified present before writing this spec.

This spec covers the two remaining tasks, shipped as **one PR**:

- **Task 2** — convention "never use `claude -p` for batch LLM work", as a
  shipped rule doc **plus** a CI tripwire.
- **Task 3** — enforce fr-isolation with an **Edit/Write PreToolUse hook**
  (marker-file based), so a session that wanders into an fr-enabled repo's
  base clone and *edits* tracked source is blocked, not merely advised.

### Operator decisions (batched Q&A, 2026-06-21)

1. Scope: **one PR**, Tasks 2 + 3 together (Task 1 confirmed already shipped).
2. Task 3 hook delivery: **plugin-registered** via
   `plugins/super-fr/hooks/hooks.json` — like the existing three hooks. The
   issue's original "operator hand-installs at `~/.claude/hooks/` + a
   `settings.json` line" assumed manual install; the plugin already
   auto-registers PreToolUse/PostToolUse hooks, so no manual step is needed.
3. Task 2: **doc + CI tripwire** (defense-in-depth, matches the principle).

## Existing surfaces (read before implementing)

- `packages/fr/src/fr/isolation/local.py` — `up()` / `down()` lifecycle; this
  is where the marker is written/removed and added to `info/exclude`.
- `packages/fr/src/fr/isolation/types.py` — `IsolationState`, `_git_common_dir`
  (the linked-worktree helper the hook's logic mirrors), `save_state`.
- `plugins/super-fr/hooks/{fr-isolation-guard,fr-pipeline-sentinel,fr-merged-pr-push-guard}.sh`
  + `hooks.json` — the precedent for a shipped, plugin-registered hook and for
  the deny-decision JSON shape.
- `tests/unit/test_hooks_guard.py` — the pattern: shell out to the `.sh` with a
  JSON payload on stdin and assert exit code / decision; env injected
  (`FR_SENTINEL_DIR`, etc.).
- `scripts/install.sh:~318` — `cp` of `plugins/super-fr/rules/*.md` into
  `~/.claude/rules/`; the new rule docs install the same way.

### Existing vs new isolation guard — complementary, not duplicate

`fr-isolation-guard.sh` is **session-sentinel + Bash-scoped**: it only fires
when *this* session ran an fr pipeline skill (sentinel present) and only denies
Bash commands. It cannot catch the issue's core failure — a session that edits
files directly in another fr-enabled repo's **base clone**, with no sentinel
for that repo. The new `fr-isolation-required.sh` is **marker-file +
Edit/Write-scoped** and **session-independent**: it fires on any edit to a
tracked-source path in an fr-enabled repo that is not inside a valid isolation
workspace. The two guards cover different tools and different trigger
conditions.

## Task 3 — fr-isolation Edit/Write enforcement

### Invariant

> Edits to tracked source/docs in an **fr-enabled** repo must happen inside an
> **fr-isolation** workspace, never the base clone.

### Marker file `.fr-isolation`

- **Written** by `fr isolation up` at the worktree root; **removed** by `down`.
- **Content** = JSON workspace identity:
  ```json
  {"toplevel": "<abs worktree path>", "branch": "<branch>", "mode": "worktree", "created_at": "<iso>"}
  ```
  `mode` is `"worktree"` for `LocalWorktreeDevcontainerTarget` (host edits land
  in a linked worktree). The field is recorded for forward-compat with a future
  container-native target (`"devcontainer"`), where the host linked-worktree
  check does not apply.
- **Leak prevention:** `up` appends `.fr-isolation` to the repo's
  `info/exclude` (under `_git_common_dir`, idempotently) so the marker is never
  staged. Belt-and-suspenders: super-fr ships `.fr-isolation` in its committed
  `.gitignore`, the repo rule instructs other repos to do the same, and a CI
  tripwire fails if `.fr-isolation` is ever tracked.

### Hook `fr-isolation-required.sh` (PreToolUse, `Edit|Write|MultiEdit|NotebookEdit`)

Decision order (fail-closed; ambiguity blocks, with explicit escapes):

1. Not one of the edit tools → **allow** (`exit 0`).
2. `FR_BASE_OK=1` in env → **allow** (deliberate base-clone edit escape hatch).
3. Extract `.tool_input.file_path`; none parseable → **allow** (hook-input
   problem, not an isolation decision — fail-open here only).
4. Resolve the file's git toplevel (walk up to the nearest existing ancestor
   dir for not-yet-created Write targets). Not in a git repo → **allow**.
5. **fr-enabled?** toplevel has `.devcontainer/<profile>/devcontainer.json`
   **or** `docs/superpowers/plans/`. Not fr-enabled → **allow**. (An OR: every
   isolation-capable repo must have a devcontainer profile — `resolve_profile`
   hard-fails without one — so `.devcontainer/` is the primary signal and the
   plans dir, which may be absent when all plans are archived, is a secondary
   heuristic. super-fr itself satisfies this via `.devcontainer/{admin,dev}/`.)
6. **Valid marker?** `<toplevel>/.fr-isolation` exists AND recorded `toplevel`
   == current resolved toplevel AND (for `mode==worktree`) the toplevel is a
   **linked worktree** — `git rev-parse --git-common-dir` ≠ `--git-dir`. Valid
   → **allow**.
7. **Exempt?** the file path matches a glob in `<toplevel>/.fr-isolation-allow`
   → **allow**.
8. Else → **deny** with a `permissionDecision: "deny"` JSON (same shape as the
   other hooks): "edit blocked — not in an fr-isolation workspace. Enter via
   `fr isolation up` / fr-goal, add the path to `.fr-isolation-allow`, or set
   `FR_BASE_OK=1` for a deliberate base edit."

### Failure modes → mitigations (all fail-closed)

| Failure | Direction | Mitigation |
|---|---|---|
| Marker committed into a PR | leak | `up` adds it to `info/exclude`; repo `.gitignore`; CI tripwire fails if tracked |
| Stale marker in base clone | false-allow (dangerous) | Linked-worktree check: main clone has `git-common-dir == git-dir` → not a worktree → block even with a marker present |
| Marker copied to another path | false-allow | Identity: recorded toplevel ≠ current toplevel → block |
| Marker missing in a legit workspace | false-block (safe) | `FR_BASE_OK=1` escape + the deny message names it |
| Container-native isolation (future) | detection gap | `mode` recorded; `mode!=worktree` skips the host linked-worktree check |

### Deliverables (Task 3)

1. `up` writes `.fr-isolation` (identity JSON) + appends to `info/exclude`;
   `down` removes the marker. (`packages/fr/src/fr/isolation/local.py`)
2. `fr-isolation-required.sh` in `plugins/super-fr/hooks/`, registered in
   `hooks.json` under a `PreToolUse` matcher `Edit|Write|MultiEdit|NotebookEdit`.
3. `.fr-isolation-allow` example globlist + `FR_BASE_OK=1` docs in the rule.
4. Shipped rule `plugins/super-fr/rules/fr-isolation-required.md` (installed to
   `~/.claude/rules/` by `install.sh` — add the `cp` line next to
   `fr-plan-override.md`) + repo-level mirror
   `.claude/rules/fr-isolation-required.md` (a **newly-created** `.claude/rules/`
   dir; auto-loads in clones incl. pods — no host-specific paths). Mirrors
   `agent-worktree-default.md`'s two-file pattern.
5. CI tripwire: a pytest asserting `.fr-isolation` is not tracked
   (`git ls-files`), running in the existing pytest gate. Plus `.fr-isolation`
   in super-fr's committed `.gitignore`.
6. Worktree-vs-devcontainer resolved via the `mode` field (above).

## Task 2 — never `claude -p` for batch LLM work

### Rule (doc)

`plugins/super-fr/rules/no-claude-p-batch.md` — installed to `~/.claude/rules/`
like `fr-plan-override.md`. Content: the rule; the measured cost (~22k input
tokens, ~$0.37, ~5s per call — each invocation cold-starts a full Claude Code
session); the ordered alternatives (1) one persistent agent session fed each
element as a turn, (2) subagent fan-out, (3) batch K elements per prompt; the
engine/transport separation principle (deterministic ops + per-item protocol
must not bake `claude -p`-per-call in); and cleanup. `claude -p` is fine only
for a single interactive/one-off call. A short pointer is added to super-fr's
`CLAUDE.md` conventions.

### CI tripwire

A pytest asserting no file under `packages/*/src/**` shells out to `claude`
with `-p` / `--print` (super-fr's packages never legitimately need to — they
are planning/isolation tooling). Runs in the existing pytest gate. This is
defense-in-depth: it guards super-fr's own code against regressing, and
demonstrates the enforce-over-prose pattern the rule preaches.

## Version & gate

- **Bump:** minor, `3.4.2 → 3.5.0` (a new mandatory enforcement hook is a
  user-visible workflow addition) via `scripts/bump-version.py minor`.
- **Gate:** `uv run ruff format packages/ tests/`,
  `uv run ruff check packages/ tests/`, `mypy` (per `ci.yml`),
  `uv run pytest -q --no-cov`, `bump-version.py --check`. New shell hook gated
  on `jq` like the existing hook tests (`pytest.mark.skipif`).

## Out of scope

- Task 1 (already shipped).
- Retrofitting the existing session-sentinel Bash guard onto the marker model
  (they remain complementary).
- A container-native isolation Target (`mode=="devcontainer"` path is recorded
  but not exercised; no such Target exists yet).

## Test Plan

None — the deliverable is pure code + docs + a plugin-registered hook (no
service/bot/infra deploy). Verification is the test suite + the CI tripwires.
