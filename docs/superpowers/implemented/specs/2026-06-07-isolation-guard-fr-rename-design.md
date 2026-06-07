# Isolation guard + fr-spelling rename — design

**Date:** 2026-06-07
**Status:** Approved
**Repo:** derio-net/super-fr
**Closes:** #265 (isolation enforcement hardening), #272 (residual vk spellings)

## Problem

1. **#265:** An fr pipeline can proceed without isolation. A real run in
   `derio-net/frank` (2026-06-06) executed measurement, exploration, and
   live-pod commands inline from the base checkout — the operator caught it.
   Root cause: skill prose phrases the contract in repo-mutation terms
   ("never touched"), leaving cluster-side/read-only ops in a gray zone, and
   no deterministic guard intercepts inline Bash the way
   `agent-worktree-required.sh` intercepts Agent dispatches.
2. **#272:** Four paths/keys still carry the pre-rebrand `vk` spelling, kept
   verbatim through the v3.0.0 split to avoid a mid-cutover fleet sweep.
   Exploration found additional residuals beyond the issue's table.

## Operator decisions (batched Q&A)

| Decision | Choice |
|---|---|
| Bash-guard strictness | **Strict** — only `fr isolation …` allowed from base-repo cwd while a pipeline is active |
| Rename scope | **Everything found** — issue's 4 surfaces + state dir + cache dir + error strings + `VK_BRIDGE_*` env vars |
| Migration surface | **`fr init migrate`** (init owns the devcontainer/profile domain) |
| Post-merge Test Plan | **Yes — both surfaces** (plugin hooks live; pod bridge lock) |

## Part 1 — Isolation enforcement (#265)

### 1a. Skill wording (fr-goal §1, fr-brainstorming §0)

Add the unconditional-first-action contract, closing the gray zone:

> Isolation precedes EVERYTHING — including read-only exploration,
> measurements, and cluster operations. An operator "start with X" changes
> the first work item, never the first action. Once the goal starts, ALL
> commands run via `fr isolation exec`.

### 1b. Plugin-shipped deterministic hook pair (the real fix)

New surface: `plugins/super-fr/hooks/hooks.json` + two bash scripts in
`plugins/super-fr/hooks/`. Plugins register hooks via `hooks/hooks.json` at
plugin root; script paths use `${CLAUDE_PLUGIN_ROOT}`
(docs: code.claude.com/docs/en/plugins-reference). Same philosophy as
`~/.claude/hooks/agent-worktree-required.sh`, extended from the Agent tool to
inline Bash.

**Sentinel writer — `fr-pipeline-sentinel.sh`** (PostToolUse, matcher `Skill`):

- Fires after every Skill call; filters inside the script on
  `tool_input.skill_name` (defensively also `.skill` / `.name` — the Skill
  tool_input field is not formally documented) matching
  `fr-goal | fr-brainstorming | fr-execute` (with or without the
  `super-fr:` namespace prefix).
- Writes `~/.cache/fr/sentinels/<session_id>.json`:
  `{"repo_root": <git toplevel of hook cwd>, "skill": ..., "started_at": ...}`.
  No-op when cwd is not inside a git repo.
- GC: on every invocation, delete sentinel files with mtime older than 48 h
  (self-expiry for dead sessions).

**Bash guard — `fr-isolation-guard.sh`** (PreToolUse, matcher `Bash`):

- Reads stdin JSON: `session_id`, `cwd`, `tool_input.command`.
- No sentinel for this session → allow (exit 0, no output).
- Sentinel present AND `realpath(cwd)` is inside sentinel `repo_root`:
  - command matches `^\s*fr\s+isolation\b` → allow; if it is
    `fr isolation down` for that repo, delete the sentinel (best-effort —
    close-out also covers it).
  - anything else → **deny** via documented JSON decision:
    `{"hookSpecificOutput": {"hookEventName": "PreToolUse",
    "permissionDecision": "deny", "permissionDecisionReason": "fr pipeline
    active: run via `fr isolation exec -- …` (or `fr isolation up` first).
    Host-side git/gh ops: run from the worktree cwd, not the base repo."}}`
- cwd outside the base repo (worktree, /tmp, …) → allow. The worktree lives
  under `~/.cache/fr/worktrees/…`, never inside the base repo.

**Sentinel lifecycle:** written at pipeline-skill invocation; cleared by
`fr isolation down` (guard-observed) and by the 48 h GC. Per-session keying
means parallel sessions in the same repo don't interfere.

**Threat model:** the guard is a discipline backstop against habit and
momentum (the #265 failure mode), not a security boundary — a compound
command prefixed with `fr isolation` could evade a prefix match, exactly as
a determined prompt could evade `agent-worktree-required.sh`. Deterministic
friction at the moment of the mistake is the goal.

**Trust note:** the operator's existing user-level PostToolUse plan-validator
hook and the new plugin hooks coexist; plugin hooks ship with the plugin
version, so the guard reaches every install at the next version bump.

## Part 2 — fr-spelling rename (#272, expanded scope)

### Rename matrix

| # | Surface | Old | New | Mechanism |
|---|---|---|---|---|
| 1 | Profiles file | `.devcontainer/vk-profiles.yaml` | `.devcontainer/fr-profiles.yaml` | dual-read, fr first, warn on vk fallback (`types.profiles_config`, `scaffold._update_profiles_yaml` writes fr) |
| 2 | Host secrets dir | `~/.config/vk/secrets/<repo>/<profile>.env` | `~/.config/fr/secrets/…` | dual-read (`local._env_file`, `scaffold.env_file_path`): use fr path; if missing AND vk path exists → use vk + warn. New scaffolds write fr; `--env-file` mount in scaffolded devcontainer.json points at fr |
| 3 | customizations key | `customizations.vk` | `customizations.fr` | scaffold writes fr; `fr init migrate` rewrites existing |
| 4 | Bridge tick lock | `/var/run/vk-bridge.lock`, `/tmp/vk-bridge.lock` | `fr-bridge.lock` (both) | direct rename — lock is transient per-tick; env override below |
| 5 | Isolation state dir | `.git/vk/isolation/` | `.git/fr/isolation/` | dual-read (`types.state_dir` et al.): load/list from fr, fall back to vk + warn; save always to fr. `fr init migrate` moves the dir |
| 6 | Worktree cache dir | `~/.cache/vk/worktrees/` | `~/.cache/fr/worktrees/` | new worktrees only — live workspaces re-address via absolute paths in their state files, so no fallback needed at creation; `status`/`exec`/`down` read paths from state |
| 7 | Error/doc strings | `vk-init`, "driven by vk-init", etc. | `fr-init` | direct fix (`types.py:83,93`, `scaffold.py:1`, `init_cmd.py`, skills) |
| 8 | Bridge env vars | `VK_BRIDGE_REPOS`, `VK_BRIDGE_LOCK_PATH`, `VK_BRIDGE_RECOVER_ORPHAN_CARDS` | `FR_BRIDGE_*` | dual-read: FR_ first, VK_ fallback + warn |
| — | **Kept:** `VK_DERIO_OPS_PROJECT_ID` (+legacy `VK_DERIO_OPS_PROJECT`) | — | — | VibeKanban-domain (names the actual VK board), not rebrand residue |
| — | **Kept:** sentinel/guard paths (Part 1) | — | — | born on fr spellings (`~/.cache/fr/sentinels`) |

### Dual-read playbook (same as the label cutover, #270)

1. This PR: fr-first reads with loud `[fr] WARNING: legacy vk path …` on
   every fallback; all writers emit fr spellings.
2. `fr init migrate` migrates a repo in place: `git mv vk-profiles.yaml
   fr-profiles.yaml`, rewrite `customizations.vk` → `.fr` and the
   `--env-file` mount in every `.devcontainer/*/devcontainer.json`, move
   `.git/vk/isolation` → `.git/fr/isolation`. Prints (does not run) an
   idempotent host command block for the operator's secrets move —
   copy-no-clobber (`mkdir -p` + `cp -an` from `~/.config/vk/secrets`), so
   running containers keep their baked `--env-file` until recreated; the vk
   dir is deleted at the fallback-removal release, not before.
3. Fleet sweep (manual phase): run `fr init migrate` in each repo with
   profiles — super-fr, frank, willikins, omada-controller (#262 sweep
   list); move host secrets on each machine; update pod env
   (`VK_BRIDGE_*` → `FR_BRIDGE_*`).
4. Fallback removal: file a follow-up issue at merge time; remove the vk
   fallbacks one minor version later (mirrors #270's removal of the label
   dual-read).

### Pod relics (manual phase, from #272)

- Delete `~/.local/bin/vk-issue-bridge.py` (pre-v2 relic) on the pod.
- Rename pod checkout `~/repos/superpowers-for-vk` → `~/repos/super-fr` and
  update the VK-board repo entry — these two move together with the
  `FR_REPOS_DIR` convention (GitHub redirects cover the interim).

## Non-goals

- No change to dispatch/tick logic, labels, or plan formats.
- No automatic host secrets move (`fr init migrate` prints, never executes,
  cross-host commands).
- No fallback removal in this PR (follow-up, one minor later).

## Versioning

Minor bump → **3.1.0**: new mandatory behavior (Bash guard), new subcommand
(`fr init migrate`), skill wording changes.

## Test Plan (post-merge — operator-driven)

1. **Hooks live:** `./scripts/install.sh` to refresh the plugin cache; in a
   scratch repo with a profile, start `/fr-goal`; verify (a) a plain Bash
   command from the base cwd is denied with the guard message, (b)
   `fr isolation exec -- echo ok` passes, (c) `fr isolation down` clears the
   sentinel and unblocks.
2. **Migration:** run `fr init migrate` on super-fr itself; verify
   `fr isolation up` works against `fr-profiles.yaml` with no fallback
   warning; run the printed secrets-move block; re-verify.
3. **Pod bridge:** after the next pod upgrade, confirm the tick log shows
   `fr-bridge.lock` and no `VK_BRIDGE_*` fallback warnings; card dispatch
   still works (one ready phase flows to a VibeKanban workspace).

## Implementation Plans

| Plan | Repo | File | Depends on |
| ---- | ---- | ---- | ---------- |
| 2026-06-07-isolation-guard-fr-rename | `derio-net/super-fr` | `2026-06-07-isolation-guard-fr-rename` | — |
