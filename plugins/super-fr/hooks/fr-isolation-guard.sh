#!/bin/bash
# PreToolUse(Bash) hook: while an fr pipeline is active (session sentinel
# present, written by fr-pipeline-sentinel.sh), deny Bash commands whose cwd
# resolves inside the pipeline's base repo — except `fr isolation …` itself.
#
# Strict mode (#265 Q&A): host-side git/gh ops run from the worktree cwd.
# A leading `cd <dir>` into an allowed prefix (fr worktrees, temp dirs) is
# the permitted transition to get there (#279).
# This is a discipline backstop against habit and momentum, not a security
# boundary. Companion: agent-worktree-required.sh (Agent-tool equivalent).

set -eu

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')
[ "$tool_name" = "Bash" ] || exit 0

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty')
[ -n "$session_id" ] || exit 0

dir="${FR_SENTINEL_DIR:-$HOME/.cache/fr/sentinels}"
sentinel="$dir/$session_id.json"
[ -f "$sentinel" ] || exit 0   # no active pipeline for this session

repo_root=$(jq -r '.repo_root // empty' "$sentinel")
[ -n "$repo_root" ] || exit 0

cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
[ -n "$cwd" ] || exit 0

# Resolve symlinks on both sides; trailing slash prevents prefix collisions
# (/x/repo must not match /x/repo-other).
rcwd=$(cd "$cwd" 2>/dev/null && pwd -P) || exit 0
rroot=$(cd "$repo_root" 2>/dev/null && pwd -P) || exit 0
case "$rcwd/" in
  "$rroot"/*) ;;        # cwd is the base repo (or inside it) — guard applies
  *) exit 0 ;;          # worktree, /tmp, elsewhere — allowed
esac

command=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')

# Transition allowance (#279): a command LEADING with `cd <dir>` whose
# target resolves inside an allowed prefix (fr worktrees, temp dirs)
# and outside the base repo is the documented way to move the host
# shell to the worktree for git/gh ops (SKILL.md exec-bridge
# discipline). Without it, a session that starts in the base repo —
# every fr pipeline session — can never reach the prescribed cwd: the
# guard would deny the very `cd` it asks for. Each subsequent call is
# re-evaluated against its own declared cwd, so nothing is lost.
cd_target=$(printf '%s' "$command" | sed -nE 's/^[[:space:]]*cd[[:space:]]+("([^"]+)"|'\''([^'\'']+)'\''|([^[:space:];&|]+)).*/\2\3\4/p')
if [ -n "$cd_target" ]; then
  case "$cd_target" in "~"*) cd_target="$HOME${cd_target#\~}" ;; esac
  if rtarget=$(cd "$cd_target" 2>/dev/null && pwd -P); then
    case "$rtarget/" in
      "$rroot"/*) ;;   # back into the base repo — guard still applies
      *)
        prefixes="${FR_CD_ALLOW_PREFIXES:-$HOME/.cache/fr/worktrees:/tmp:${TMPDIR:-}}"
        old_ifs=$IFS
        IFS=':'
        for prefix in $prefixes; do
          [ -n "$prefix" ] || continue
          rprefix=$(cd "$prefix" 2>/dev/null && pwd -P) || continue
          case "$rtarget/" in
            "$rprefix"/*) IFS=$old_ifs; exit 0 ;;
          esac
        done
        IFS=$old_ifs
        ;;
    esac
  fi
fi

# Bootstrap + read-only fr commands are allowed even from the base-repo cwd:
# `fr init …` is the host-side scaffold the gate's own error chain points to —
# without it a fresh repo with no devcontainer profile can never bootstrap an
# fr-goal run (the deadlock in super-fr#299). `fr --version` / `fr skills` are
# harmless info commands. Everything else (fr plan, fr apply, …) still routes
# through the worktree.
if printf '%s' "$command" | grep -Eq '^[[:space:]]*fr[[:space:]]+(init([[:space:]]|$)|skills([[:space:]]|$)|--version([[:space:]]|$))'; then
  exit 0
fi

if printf '%s' "$command" | grep -Eq '^[[:space:]]*fr[[:space:]]+isolation([[:space:]]|$)'; then
  # The isolation lifecycle itself is the one allowed surface; `down` ends
  # the pipeline, so retire the sentinel (best-effort).
  if printf '%s' "$command" | grep -Eq '^[[:space:]]*fr[[:space:]]+isolation[[:space:]]+down([[:space:]]|$)'; then
    rm -f "$sentinel" || true
  fi
  exit 0
fi

# Self-heal (#341 Task 2A): if the pipeline's sentinel has outlived all
# worktrees, the `cd <worktree>` escape below is unsatisfiable — denying is pure
# deadlock. Detect zero linked worktrees via a SUCCESSFUL `git worktree list`
# (exactly one `worktree ` line = the main checkout) and fail open, clearing the
# orphaned sentinel so the next command sees no active pipeline. Gated on git
# success so a non-git cwd fails closed (keeps the discipline; the `fr isolation
# down --all` escape and the guard tests both rely on this). Companion:
# clear_repo_sentinels() in fr/isolation/types.py (the eager, explicit lever).
if wt=$(git -C "$rroot" worktree list --porcelain 2>/dev/null); then
  n=$(printf '%s\n' "$wt" | grep -c '^worktree ' || true)
  if [ "${n:-0}" -eq 1 ]; then
    rm -f "$sentinel" || true
    exit 0
  fi
fi

jq -n --arg reason "fr pipeline active — ALL base-repo commands are gated (not just git/gh), so work runs in the isolation worktree. Run via \`fr isolation exec -- …\` (or \`fr isolation up\` first), or lead with \`cd <worktree> && …\` to work from the worktree cwd. No worktree left? \`fr isolation down --all\` clears the pipeline. See plugins/super-fr/skills/fr-isolation (exec-bridge discipline, #265/#279/#329)." \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
exit 0
