#!/bin/bash
# PreToolUse(Bash) hook: while an fr pipeline is active (session sentinel
# present, written by fr-pipeline-sentinel.sh), deny Bash commands whose cwd
# resolves inside the pipeline's base repo — except `fr isolation …` itself.
#
# Strict mode (#265 Q&A): host-side git/gh ops run from the worktree cwd.
# A leading `cd <dir>` into an allowed prefix (fr worktrees, temp dirs) is
# the permitted transition to get there (#279).
#
# Scoped by TARGET as well as cwd (#421): a leading `cd` into a genuine fr
# ISOLATION WORKSPACE (valid `.fr-isolation` marker — this repo's worktree or
# another repo's) is allowed outright. NOT "any different git repo": that was
# the first cut, and it puts `~/.ssh` one `cd` away on any machine whose $HOME
# is a dotfiles repo. Everything else falls through to the allowed-prefix loop
# and the `fr …` allowances, which are matched after a leading `cd` INTO A REPO
# is stripped, so `cd <other-repo> && fr isolation up` composes. Without both,
# the two escapes this hook offers were mutually exclusive and a second repo was
# unreachable from a live pipeline — including via the very command the deny
# message recommends.
#
# Only the FIRST LINE of a command is ever evaluated. sed/grep anchor `^` per
# line, so without this a multi-line command — including a heredoc that merely
# quotes `fr isolation down` in prose — would satisfy an allowance on some
# later line and, worse, retire the sentinel.
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
      # Back into the base repo — guard still applies, but the `fr …`
      # allowances below may compose with this `cd` (journal p3-f1: `fr
      # isolation up` from the base cwd is already permitted, so denying it
      # merely because a same-repo `cd` preceded it would be arbitrary).
      "$rroot"/*) cd_strip=1 ;;
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
        # outside $rroot and lands here. It is admitted when it carries a valid
        # marker or sits under the prefix list — the usual case, so behaviour
        # is unchanged there. When it does neither it is denied, and
        # `cd_same_repo_worktree` (set above) keeps that deny from calling it
        # "another repo" and telling the caller to cut a worktree of it
        # (rev2-f4).
        #
        # "Not THIS pipeline's business" is NOT "anything goes". The allowance
        # #421 needs is narrow: REACH another repo's isolation. It is not
        # "cd anywhere and run anything", and the difference is not academic —
        # `$HOME` is a git repo on any machine with a dotfiles repo, so
        # "allow any different git repo" puts `~/.ssh` one `cd` away from a
        # session that could not touch it a moment earlier.
        #
        # So the destination must be a GENUINE fr isolation workspace — a valid
        # `.fr-isolation` marker, this repo's worktree or another repo's.
        # Everything else falls through, where:
        #   - the allowed-prefix loop below still admits fr worktrees / temp dirs;
        #   - the `fr …` allowances still fire, so `cd <repo-B> && fr isolation
        #     up` works. Reaching repo B's isolation is the whole ask of #421,
        #     and it never required repo B's base clone to be usable.
        # The deny is therefore a discipline, not a deadlock.
        #
        # NOTE this is deliberately stricter than `fr_isolation_decide_cwd`,
        # which answers 0 for any non-fr repo. That is right for the edit gate
        # (no business in a repo that never opted into fr) and wrong here (see
        # the dotfiles case above).
        if rtop=$(git -C "$rtarget" rev-parse --show-toplevel 2>/dev/null) &&
           rtop=$(cd "$rtop" 2>/dev/null && pwd -P) && [ -n "$rtop" ]; then
          # The `fr …` allowances may compose with a `cd` that lands on a repo
          # TOPLEVEL — that is the shape #421 needs (`cd <repo-B> && fr
          # isolation up`). A `cd` to a mere subdirectory of some other repo is
          # NOT that shape, and admitting it is how `~/.ssh` became reachable
          # on a dotfiles-$HOME machine (rev2-f1).
          if [ "$rtop" = "$rtarget" ]; then cd_strip=1; fi
          # Same repository, different linked worktree? Then the cross-repo
          # deny message would misname it "another repo" and tell the caller to
          # cut a worktree of it (rev2-f4).
          if tcommon=$(git -C "$rtarget" rev-parse --git-common-dir 2>/dev/null) &&
             tcommon=$(cd "$rtarget" && cd "$tcommon" 2>/dev/null && pwd -P) &&
             rcommon=$(git -C "$rroot" rev-parse --git-common-dir 2>/dev/null) &&
             rcommon=$(cd "$rroot" && cd "$rcommon" 2>/dev/null && pwd -P) &&
             [ "$tcommon" = "$rcommon" ]; then
            cd_same_repo_worktree=1
          fi
          case "$rtop/" in
            "$rroot"/*) ;;   # same repo after all — keep guarding
            *)
              # Recorded whether or not it is allowed: it suppresses the
              # sentinel retirement below (a `fr isolation down` aimed at
              # ANOTHER repo must not end THIS repo's pipeline) and gives the
              # deny a reason that names the right repo — emitting repo A's
              # "pipeline active" text here would point at the wrong worktree,
              # the same misleading-remedy failure #421 was filed about.
              cd_other_repo=$rtop
              if [ "${FR_BASE_OK:-}" = "1" ] || fr_isolation_marker_valid "$rtarget"; then
                exit 0
              fi
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

# What the `fr …` allowances below are matched against: the FIRST LINE of the
# command, with a leading `cd <dir> &&|;` stripped when that `cd` landed
# somewhere the allowances may legitimately compose with (#421) — inside the
# base repo, or on another repo's TOPLEVEL. Before the strip existed, a command
# that had to LEAD with `cd` to be in the right place could never match the
# start-anchored allowances, so the two escapes the deny message offers were
# mutually exclusive.
#
# The strip is GATED (rev2-f1) because these allowances are start-anchored but
# not end-anchored: anything after `&&` rides along. Stripping unconditionally
# extended that rider to any `cd` target at all, which measurably put `~/.ssh`
# back in reach of a live pipeline (DENY -> ALLOW for
# `cd ~/.ssh && fr isolation status && cat id_ed25519`). Gating costs nothing
# #421 needs: its ask is always a repo.
#
# Only a LEADING cd is stripped, so `echo x && cd <dir> && …` matches nothing
# and stays denied.
#
# NOTE: a different repo has NOT necessarily exited above — a non-workspace
# repo deliberately falls through so `cd <repo-B> && fr isolation up` can
# compose. `cd_other_repo` is set in that case, and the retirement test below
# is what keeps another repo's `down` from ending THIS pipeline. Ordering does
# not protect the sentinel; that test does. Do not delete it.
rest=$(printf '%s' "$command" | head -n 1)
if [ "${cd_strip:-0}" = 1 ]; then
  rest=$(printf '%s' "$rest" | sed -E 's/^[[:space:]]*cd[[:space:]]+("[^"]+"|'\''[^'\'']+'\''|[^[:space:];&|]+)[[:space:]]*(&&|;)[[:space:]]*//')
fi

# An `fr …` command is still an `fr …` command behind an env prefix or `uv run`
# (rev2-f3). `FR_ISOLATION_TARGET=worktree fr isolation up` is THE docker-less
# form, and denying it left the deny message recommending a remedy that only
# worked in repos which already had a devcontainer profile — the #421 defect
# class one layer out. Stripping only feeds the matchers below: a non-`fr`
# command behind the same prefix still fails them and is still denied.
rest=$(printf '%s' "$rest" | sed -E \
  -e 's/^[[:space:]]*(env[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)+//' \
  -e 's/^[[:space:]]*uv[[:space:]]+run[[:space:]]+//')

# Bootstrap + read-only fr commands are allowed even from the base-repo cwd:
# `fr init …` is the host-side scaffold the gate's own error chain points to —
# without it a fresh repo with no devcontainer profile can never bootstrap an
# fr-goal run (the deadlock in super-fr#299). `fr --version` / `fr skills` are
# harmless info commands. Everything else (fr plan, fr apply, …) still routes
# through the worktree.
if printf '%s' "$rest" | grep -Eq '^[[:space:]]*fr[[:space:]]+(init([[:space:]]|$)|skills([[:space:]]|$)|--version([[:space:]]|$))'; then
  exit 0
fi

# Retiring the sentinel ENDS the live pipeline, so it must be POSITIVELY aimed
# at this repo; "not obviously aimed elsewhere" is not enough (rev2-f2). Shapes
# that previously ended the pipeline from a command meant for somewhere else:
#   * `fr isolation down --repo <other>` — fr's own way to aim `down` elsewhere.
#     The Python mirror, clear_repo_sentinels(), is careful about exactly this
#     ("foreign-repo sentinels are left alone"); this guard was not.
#   * `cd $VAR && fr isolation down` — the hook performs no shell expansion, so
#     the target never resolved and the cross-repo flag was never set, while the
#     strip still fired and the match still succeeded.
#   * any multi-line command, including a heredoc merely quoting the command in
#     prose — now excluded upstream by the first-line rule.
# Fails CLOSED: a sentinel that lingers is self-healed when the last worktree
# goes (#341, below), whereas a pipeline ended by mistake is not recoverable.
down_targets_this_repo() {
  [ -z "${cd_other_repo:-}" ] || return 1
  if [ -n "${cd_target:-}" ] && [ -z "${rtarget:-}" ]; then return 1; fi

  _repo_opt=$(printf '%s' "$rest" |
    sed -nE 's/.*--repo[=[:space:]][[:space:]]*("([^"]+)"|'\''([^'\'']+)'\''|([^[:space:]]+)).*/\2\3\4/p')
  [ -n "$_repo_opt" ] || return 0

  case "$_repo_opt" in "~"*) _repo_opt="$HOME${_repo_opt#\~}" ;; esac
  _rtop=$(cd "$_repo_opt" 2>/dev/null && pwd -P) || return 1
  _rtop=$(git -C "$_rtop" rev-parse --show-toplevel 2>/dev/null) || return 1
  _rtop=$(cd "$_rtop" 2>/dev/null && pwd -P) || return 1
  [ "$_rtop" = "$rroot" ]
}

if printf '%s' "$rest" | grep -Eq '^[[:space:]]*fr[[:space:]]+isolation([[:space:]]|$)'; then
  # The isolation lifecycle itself is the one allowed surface; `down` ends the
  # pipeline, so retire the sentinel (best-effort) — but only when it is this
  # repo's pipeline being ended.
  if printf '%s' "$rest" | grep -Eq '^[[:space:]]*fr[[:space:]]+isolation[[:space:]]+down([[:space:]]|$)' &&
     down_targets_this_repo; then
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

if [ -n "${cd_same_repo_worktree:-}" ]; then
  # Same repository, different linked worktree — NOT "another repo". Naming it
  # one, and recommending `fr isolation up` inside it, is incoherent (rev2-f4).
  reason="fr-isolation: \`${cd_other_repo:-${rtarget:-}}\` is a linked worktree of THIS repo, but it carries no valid \`.fr-isolation\` marker, so it is not an isolation workspace. Run \`fr isolation up --branch <branch>\` (allowed from here) and work from the workspace it reports, or add this path to FR_CD_ALLOW_PREFIXES if it is a worktree you manage yourself. See plugins/super-fr/rules/fr-isolation-required.md."
elif [ -n "${cd_other_repo:-}" ]; then
  # The command hopped to ANOTHER repo that is not an isolation workspace.
  # Name that repo and its own remedy: repo A's "pipeline active" text would
  # misattribute the block and point at the wrong worktree.
  #
  # Only recommend `fr isolation up` where it can actually succeed. In a repo
  # with no devcontainer profile, resolve_profile() hard-raises rather than
  # degrading to unisolated — recommending it there would print a remedy that
  # cannot work, which is the #421 defect this hook exists to have fixed
  # (rev2-f3).
  if _fr_is_enabled "$cd_other_repo" 2>/dev/null; then
    reason="fr-isolation: \`$cd_other_repo\` is not an fr isolation workspace (no valid \`.fr-isolation\` marker), so a live pipeline elsewhere does not open it for general work — reaching another repo is for entering ITS isolation, not for running anything there. Do: \`cd $cd_other_repo && fr isolation up --branch <branch>\` (allowed from here; prefix \`FR_ISOLATION_TARGET=worktree\` if that repo has no devcontainer profile), then run the command from the worktree it reports. See plugins/super-fr/rules/fr-isolation-required.md (#421)."
  else
    reason="fr-isolation: \`$cd_other_repo\` is not fr-managed, so there is no isolation to enter and this hook has no opinion about that repo's own tooling — the deny is only about a live pipeline in \`$rroot\` reaching sideways mid-run. Finish or end this pipeline (\`fr isolation down\`), or run the command from a session that holds no pipeline. FR_BASE_OK=1 also disables the gate, but the hook reads it from its OWN environment: an inline \`FR_BASE_OK=1 <cmd>\` is not parsed, so it has to be set where the harness is launched. See plugins/super-fr/rules/fr-isolation-required.md (#421)."
  fi
else
  reason="fr pipeline active — ALL base-repo commands are gated (not just git/gh), so work runs in the isolation worktree. Run via \`fr isolation exec -- …\` (or \`fr isolation up\` first), or lead with \`cd <worktree> && …\` to work from the worktree cwd. Working in a DIFFERENT repo? \`cd <other-repo> && fr isolation up\` is allowed from here (prefix \`FR_ISOLATION_TARGET=worktree\` if that repo has no devcontainer profile) — enter that repo's isolation and work from its worktree. No worktree left? \`fr isolation down --all\` clears the pipeline. See plugins/super-fr/skills/fr-isolation (exec-bridge discipline, #265/#279/#329/#421)."
fi

jq -n --arg reason "$reason" \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
exit 0
