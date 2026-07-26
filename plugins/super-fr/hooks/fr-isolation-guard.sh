#!/bin/bash
# PreToolUse(Bash) hook: while an fr pipeline is active (session sentinel
# present, written by fr-pipeline-sentinel.sh), deny Bash commands whose cwd
# resolves inside the pipeline's base repo — except `fr isolation …` itself.
#
# Strict mode (#265 Q&A): host-side git/gh ops run from the worktree cwd.
# A leading `cd <dir>` into an allowed prefix (fr worktrees, temp dirs) is
# the permitted transition to get there (#279).
#
# Scoped by TARGET as well as cwd (#421): a leading `cd` into a DIFFERENT git
# repo is allowed outright, and the `fr …` allowances are matched after that
# leading `cd` is stripped, so `cd <other-repo> && fr isolation up` composes.
# Without both, the two escapes this hook offers were mutually exclusive and a
# second repo was unreachable from a live pipeline — including via the very
# command the deny message recommends.
#
# This is a discipline backstop against habit and momentum, not a security
# boundary. Companion: agent-worktree-required.sh (Agent-tool equivalent) and
# fr-phase-executor-guard.sh (refuses the poisoned phase dispatch, #420).

set -eu

# The marker / fr-enabled decision is shared with the edit gate and the Hermes
# bash guard, in one tested library — `fr_isolation_decide_cwd` answers "is this
# directory an allowed context, or an fr-enabled base clone with no valid
# marker?". This entrypoint owns the sentinel, the cwd scoping, and the deny JSON.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/fr-isolation-decision.sh
. "$SCRIPT_DIR/lib/fr-isolation-decision.sh"

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
#
# ONLY the leading `cd` is ever evaluated. `cd /tmp && cd <elsewhere> && …`
# therefore satisfies the allowance on its first segment and slips the rest
# through. That is deliberate and pinned by name in the tests (#421 asked for
# it to be closed or blessed; it is blessed): this is a discipline backstop
# against habit and momentum, not a security boundary, and a determined prompt
# was never in scope.
cd_target=$(printf '%s' "$command" | sed -nE 's/^[[:space:]]*cd[[:space:]]+("([^"]+)"|'\''([^'\'']+)'\''|([^[:space:];&|]+)).*/\2\3\4/p')
if [ -n "$cd_target" ]; then
  case "$cd_target" in "~"*) cd_target="$HOME${cd_target#\~}" ;; esac
  if rtarget=$(cd "$cd_target" 2>/dev/null && pwd -P); then
    case "$rtarget/" in
      "$rroot"/*) ;;   # back into the base repo — guard still applies
      *)
        # Scope the deny by TARGET, not only by cwd (#421). The harness
        # reports the SESSION cwd as `.cwd` whatever the command does, so a
        # pipeline session's cwd is always its base repo and the guard always
        # engages. But the guard's whole purpose is "commands whose cwd
        # resolves inside THE PIPELINE'S base repo" — another git repo is
        # simply not that repo, and the pipeline's discipline does not reach
        # it. Without this, a session holding a pipeline in repo A cannot
        # start isolation in repo B at all: the prefix list below never admits
        # another repo, and the `fr isolation` allowance could not compose
        # with the leading `cd` needed to get there. That made fr-goal §3 —
        # one agent per repo for a cross-repo spec — unreachable.
        #
        # A linked worktree of the SAME base repo also reports a toplevel
        # outside $rroot and is admitted here. That is the intended
        # destination anyway (it was already allowed by the prefix list), so
        # behaviour is unchanged.
        #
        # "Not THIS pipeline's business" is NOT "nobody's business". Repo B has
        # its own isolation discipline, and dropping it would turn this
        # allowance into "cd anywhere and do anything" — letting a session
        # mutate another fr-enabled repo's UN-ISOLATED base clone, precisely
        # what fr-isolation exists to prevent. So the target is handed to the
        # shared `fr_isolation_decide_cwd`, the same check the edit gate and the
        # Hermes bash guard already apply (its docstring says "used by both the
        # edit gate and the bash guard" — this guard was the one that didn't):
        #
        #   allowed context  — a worktree, a non-fr repo, or a valid marker, or
        #                      FR_BASE_OK=1 → allow, #421 satisfied.
        #   blocked context  — fr-enabled base clone, no marker → repo B's OWN
        #                      discipline stands. Fall through: the `fr …`
        #                      allowances below still fire, so `cd <repo-B> &&
        #                      fr isolation up` works. That is the whole ask of
        #                      #421 — reach repo B's isolation — and it does not
        #                      require repo B's base clone to be writable.
        if rtop=$(git -C "$rtarget" rev-parse --show-toplevel 2>/dev/null) &&
           rtop=$(cd "$rtop" 2>/dev/null && pwd -P) && [ -n "$rtop" ]; then
          case "$rtop/" in
            "$rroot"/*) ;;   # same repo after all — keep guarding
            *)
              if fr_isolation_decide_cwd "$rtarget"; then
                exit 0       # different repo, and its own discipline is satisfied
              fi
              # Blocked by repo B's OWN discipline, not repo A's pipeline.
              # Recorded so the deny can say so: reporting repo A's "pipeline
              # active" message here would misattribute the block and point at
              # the wrong worktree — the same class of misleading-remedy bug
              # #421 was filed about.
              other_repo_blocked=$rtop
              ;;
          esac
        fi
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

# The command with a leading `cd <dir> &&|;` stripped (#421). The `fr …`
# allowances below are start-anchored, so before this a command that had to
# LEAD with `cd` to be in the right place could never match them — the two
# escapes the deny message offers were mutually exclusive. Stripping is only
# ever of a LEADING cd, so `echo x && cd <dir> && …` still matches nothing and
# is still denied.
#
# Reached only when the cd target is inside the base repo (or there is no cd),
# so this composes the allowances WITHIN the pipeline's own repo; a different
# repo has already exited above. That ordering is what keeps `cd <other-repo>
# && fr isolation down` from retiring THIS repo's sentinel.
rest=$(printf '%s' "$command" | sed -E 's/^[[:space:]]*cd[[:space:]]+("[^"]+"|'\''[^'\'']+'\''|[^[:space:];&|]+)[[:space:]]*(&&|;)[[:space:]]*//')

# Bootstrap + read-only fr commands are allowed even from the base-repo cwd:
# `fr init …` is the host-side scaffold the gate's own error chain points to —
# without it a fresh repo with no devcontainer profile can never bootstrap an
# fr-goal run (the deadlock in super-fr#299). `fr --version` / `fr skills` are
# harmless info commands. Everything else (fr plan, fr apply, …) still routes
# through the worktree.
if printf '%s' "$rest" | grep -Eq '^[[:space:]]*fr[[:space:]]+(init([[:space:]]|$)|skills([[:space:]]|$)|--version([[:space:]]|$))'; then
  exit 0
fi

if printf '%s' "$rest" | grep -Eq '^[[:space:]]*fr[[:space:]]+isolation([[:space:]]|$)'; then
  # The isolation lifecycle itself is the one allowed surface; `down` ends
  # the pipeline, so retire the sentinel (best-effort).
  if printf '%s' "$rest" | grep -Eq '^[[:space:]]*fr[[:space:]]+isolation[[:space:]]+down([[:space:]]|$)'; then
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

if [ -n "${other_repo_blocked:-}" ]; then
  # Blocked by the TARGET repo's own isolation discipline. Naming the right
  # repo and the right remedy matters: this is not repo A's pipeline talking.
  reason="fr-isolation: \`$other_repo_blocked\` is an fr-enabled base clone with no valid \`.fr-isolation\` marker, so its own isolation discipline applies — a pipeline in another repo does not exempt it. Enter ITS isolation first (\`cd $other_repo_blocked && fr isolation up --branch <branch>\`, which this guard allows) and run the command from that worktree; or set FR_BASE_OK=1 for one deliberate base-clone command. See plugins/super-fr/rules/fr-isolation-required.md (#421)."
else
  reason="fr pipeline active — ALL base-repo commands are gated (not just git/gh), so work runs in the isolation worktree. Run via \`fr isolation exec -- …\` (or \`fr isolation up\` first), or lead with \`cd <worktree> && …\` to work from the worktree cwd. Working in a DIFFERENT repo? Lead with \`cd <other-repo> && …\` — this pipeline gates only its own base repo (that repo's own isolation still applies, and \`cd <other-repo> && fr isolation up\` is always allowed). No worktree left? \`fr isolation down --all\` clears the pipeline. See plugins/super-fr/skills/fr-isolation (exec-bridge discipline, #265/#279/#329/#421)."
fi

jq -n --arg reason "$reason" \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
exit 0
