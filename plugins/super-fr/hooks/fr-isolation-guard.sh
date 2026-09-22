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

# Liveness: every Bash call this session makes — from the base clone, the
# worktree or anywhere — refreshes the sentinel's mtime, so its age means "time
# since this session last did anything". The 48h GC (fr-pipeline-sentinel.sh)
# keys on that age; without this refresh it deleted a LIVE pipeline's sentinel
# once 48h passed with no skill load or bind, and the guard silently switched
# off. `-c`: never create — a sentinel retired since the test above stays gone.
touch -c "$sentinel" 2>/dev/null || true

# `|| exit 0`: the sentinel can vanish between the test above and this read
# (another session's `down`, the 48h GC) or be caught mid-write. Under `set -e`
# jq's failure would exit non-zero, which the harness treats as a BLOCK — a
# spurious deny for a pipeline that no longer exists (review L3).
repo_root=$(jq -r '.repo_root // empty' "$sentinel" 2>/dev/null) || exit 0
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

# The pipeline's repo may ITSELF be the isolation workspace: external mode, where
# a preparer (k8s operator, image build) hands over a PRIMARY checkout carrying a
# `mode: external` marker. There is no linked worktree to cut and nothing to
# stamp, so its sentinel is fresh for good — and a fresh sentinel is never
# healed (#529). The count heal used to retire it on the first command, by
# accident; without this, every command in the only checkout the session has
# would be denied. Validated by the SAME predicate the edit gate trusts: a
# `worktree`-mode marker cannot pass in a primary checkout, and an `external`
# one needs live container evidence, so a marker copied into a host's base
# clone never opens it. Allowed, not retired: the pipeline is still live.
if fr_isolation_marker_valid "$rroot"; then
  exit 0
fi

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
# FIRST LINE only, like everything else here: sed prints a match per line, so
# a second line that also began with `cd` was glued onto this target, which then
# resolved nowhere (and was reported as a path that "no longer exists").
cd_target=$(printf '%s\n' "$command" | head -n 1 | sed -nE 's/^[[:space:]]*cd[[:space:]]+("([^"]+)"|'\''([^'\'']+)'\''|([^[:space:];&|]+)).*/\2\3\4/p')
if [ -n "$cd_target" ]; then
  case "$cd_target" in "~"*) cd_target="$HOME${cd_target#\~}" ;; esac
  # A relative target is relative to the SESSION's cwd, which is what the shell
  # will `cd` from — not to this hook process's cwd, which the harness chooses.
  # Resolved against the latter, `cd tests && …` was judged by whichever
  # `tests/` the hook happened to be launched beside (it could even land in an
  # fr worktree and be admitted outright). Anchored once, here, so every use
  # below — the transition allowance, `down`'s aim, the gone-path message —
  # agrees on which directory the command means.
  case "$cd_target" in /*) ;; *) cd_target="$rcwd/$cd_target" ;; esac
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
# compose. That is safe for the sentinel because this hook no longer retires it
# on ANY command it allows (see the `fr isolation` allowance below).
rest=$(printf '%s' "$command" | head -n 1)
if [ "${cd_strip:-0}" = 1 ]; then
  rest=$(printf '%s' "$rest" | sed -E 's/^[[:space:]]*cd[[:space:]]+("[^"]+"|'\''[^'\'']+'\''|[^[:space:];&|]+)[[:space:]]*(&&|;)[[:space:]]*//')
fi

# An `fr …` command is still an `fr …` command behind an env prefix or `uv run`
# (rev2-f3; the strip lives in the lib so the session-bind hook uses the same one). `FR_ISOLATION_TARGET=worktree fr isolation up` is THE docker-less
# form, and denying it left the deny message recommending a remedy that only
# worked in repos which already had a devcontainer profile — the #421 defect
# class one layer out. Stripping only feeds the matchers below: a non-`fr`
# command behind the same prefix still fails them and is still denied.
rest=$(fr_strip_command_prefix "$rest")   # lib: shared with fr-session-bind.sh

# Bootstrap + read-only fr commands are allowed even from the base-repo cwd:
# `fr init …` is the host-side scaffold the gate's own error chain points to —
# without it a fresh repo with no devcontainer profile can never bootstrap an
# fr-goal run (the deadlock in super-fr#299). `fr --version` / `fr skills` are
# harmless info commands. Everything else (fr plan, fr apply, …) still routes
# through the worktree.
if printf '%s' "$rest" | grep -Eq '^[[:space:]]*fr[[:space:]]+(init([[:space:]]|$)|skills([[:space:]]|$)|--version([[:space:]]|$))'; then
  exit 0
fi

# `fr run start` ENTERS isolation, exactly as `fr isolation up` does: it calls
# ensure_run_workspace before it writes anything, and the run file lands inside
# the worktree (fr.run.workspace, review fix r2-f5). fr-goal makes it the FIRST
# action, so denying it from the base clone made the skill's first instruction
# unexecutable on Claude Code — but only in a repo that already had some linked
# worktree; with none, the COUNT-based heal this file used to carry retired the
# sentinel first, which is why this hid. That heal is gone (#529: a fresh
# pipeline IS the zero-worktree case), so this allowance is now the only thing
# keeping the skill's first action executable. `start` ONLY: `adopt`
# deliberately writes where it is run, and
# every other run verb belongs in the workspace `start` prints. It does not
# retire the sentinel — entering a pipeline is not ending one.
if printf '%s' "$rest" | grep -Eq '^[[:space:]]*fr[[:space:]]+run[[:space:]]+start([[:space:]]|$)'; then
  exit 0
fi

# The isolation lifecycle itself is the one allowed surface. This hook does
# NOT retire the sentinel on `fr isolation down` — it used to, and that was
# wrong in a way no amount of aiming could fix (adversarial review H2): the hook
# runs BEFORE the command, so it ended the pipeline for a `down` that then
# REFUSED (open PR, dirty worktree, unlanded content — #467), for `down --branch
# <another session's>`, and for `down --help`. rev2-f2 had already closed the
# cases aimed at another repo; these were aimed at this one and still wrong.
# `fr isolation down` retires exactly the sentinels of the workspace it tore
# down, AFTER it succeeds (`clear_workspace_sentinels`), from whatever cwd it
# runs in — which removes the #399 reason this hook ever did it.
if printf '%s' "$rest" | grep -Eq '^[[:space:]]*fr[[:space:]]+isolation([[:space:]]|$)'; then
  exit 0
fi

# Self-heal (#341 Task 2A, rebuilt for #472/#529): if every workspace this
# session bound is gone, the `cd <worktree>` escape below is unsatisfiable and
# denying is pure deadlock. The decision is PER SENTINEL and reads a RECORDED
# fact, never a repo-wide count.
#
# The count it replaces (`grep -c '^worktree '` == 1, i.e. "no linked worktree
# survives") was a proxy for a per-session question, and it failed in BOTH
# directions:
#   * #472 — never heals. ANY other session's worktree, or a Claude subagent
#     checkout, keeps the count above one, so a session whose own workspace was
#     reaped stayed locked out of every base-clone command.
#   * #529 — heals too eagerly. A FRESH pipeline has not cut its worktree yet,
#     so the count is also one: the first base-repo command (`ls` included)
#     retired the sentinel and silently disarmed the guard for the whole
#     session. That is why #508's `fr run start` deny only reproduced in a repo
#     that already had some worktree.
# The two cannot both be fixed by any count: "never had a workspace" versus
# "had one, lost it" is not inferable from `git worktree list`.
#
# So the sentinel records it. `fr.isolation.types.stamp_sentinel_workspace`
# (called from `attach`, the one place a session is bound) adds to `workspaces`
# every workspace of THIS repo the session binds, each RELATIVE to
# `${HOME}/.cache/fr`. It is a set because a session may bind more than one
# (`fr isolation exec --branch <other>` rebinds); judging one replaced stamp let
# the other workspace's reaping disarm this session's live pipeline (review C1).
# Three states:
#   fresh     — no entries. Armed, never healed. A legacy sentinel and an
#               unstampable workspace (outside the cache dir) read as fresh:
#               fail-closed, bounded by `fr isolation down` and the 48h GC.
#   live      — at least one entry exists AND is a listed linked worktree of
#               this repo. Armed.
#   orphaned  — entries, and none of them is. Retire THIS sentinel only
#               (another session's is not ours to remove) and allow.
# Both sides of the path comparison are `pwd -P`'d: on macOS `$HOME` and
# `$TMPDIR` are reached through symlinks, and an unresolved compare reads a
# live workspace as orphaned — the #529 disarm by another route.
# A FAILED `git worktree list` (non-git cwd) is unknown, not orphaned: it falls
# through and denies, as it always has.
sentinel_workspaces() {
  jq -r '(.workspaces // []) | if type == "array" then .[] else empty end
         | select(type == "string" and . != "")' "$sentinel" 2>/dev/null || true
}
# Unlocked peek first: a fresh sentinel (the common case) never takes the lock.
# The decision itself is made UNDER the lock shared with every other writer
# (fr_sentinel_lock): the heal deletes, and a bind landing between a read and
# the delete can turn "orphaned" back into "live" — deciding on a stale read
# would retire a live pipeline.
# The guard is the hot path (every Bash call), so it waits at most ~1s (20
# steps) — a healthy holder keeps the lock for milliseconds. A lock it cannot
# get means no heal THIS call: the sentinel stays armed (the fail-closed side)
# and a later call heals. It never breaks a live holder. (At ~5s, a lock left
# ownerless by a crashed writer cost every Bash call a 5s stall until it aged
# past 60s — found by re-running the reviewer's reproduction.)
if [ -n "$(sentinel_workspaces)" ] && fr_sentinel_lock "$sentinel" 20; then
  # Everything the verdict reads is read HERE, under the lock — the entries and
  # the worktree list alike. Listing first and locking second let a workspace
  # created while we waited read as "not listed", i.e. orphaned.
  workspaces=$(sentinel_workspaces)
  live=1   # unknown (non-git repo, or emptied/retired while we waited): no heal
  if [ -n "$workspaces" ] && wt=$(git -C "$rroot" worktree list --porcelain 2>/dev/null); then
    listed=""
    while IFS= read -r line; do
      case "$line" in
        "worktree "*)
          if rwt=$(cd "${line#worktree }" 2>/dev/null && pwd -P); then
            listed="$listed$rwt
"
          fi
          ;;
      esac
    done <<< "$wt"   # herestring, not a heredoc: a path with a `$` in it is
                     # data here, never re-expanded — and the loop must stay in
                     # THIS shell, so a pipe is not an option ($listed).
    live=0
    while IFS= read -r ws; do
      rws=$(cd "$HOME/.cache/fr/$ws" 2>/dev/null && pwd -P) || continue   # gone
      case "
$listed" in
        *"
$rws
"*) live=1; break ;;
      esac
    done <<< "$workspaces"
  fi
  # Compare before delete: still ours? A lock can only be taken from a DEAD
  # holder, so this holds unless we were presumed dead — and then the read we
  # decided on may be stale, so we do not act on it.
  if [ "$live" -eq 0 ] && fr_sentinel_owns "$sentinel"; then
    rm -f "$sentinel" || true
    fr_sentinel_unlock "$sentinel"
    exit 0
  fi
  fr_sentinel_unlock "$sentinel"
fi

if [ -n "${cd_target:-}" ] && ! [ -d "$cd_target" ]; then
  # #432: the prescribed escape is `cd <worktree>`, and the commonest reason it
  # fails is that the worktree is GONE — fr removes a workspace once its branch
  # merges, and the 48h GC reaps the rest. Answering that with the generic "work
  # in the worktree" text sends the operator back to a path that no longer
  # exists. `cd_target` has already been tilde-expanded above; an unexpanded
  # `$VAR` lands here too, which is honest enough (the hook performs no shell
  # expansion, so that path really is not a directory it can see).
  reason="fr-isolation: \`$cd_target\` no longer exists, so this \`cd\` cannot succeed — an fr workspace is removed once its branch merges, and unused ones are GC'd after 48h. Where are this session's live workspaces? \`fr isolation status\`. Start a fresh one with \`fr isolation up --branch <name>\` (prefix \`FR_ISOLATION_TARGET=worktree\` if this repo has no devcontainer profile) and work from the path it reports; \`fr isolation exec -- …\` runs a one-off there. A live pipeline still gates base-repo commands — that part is unchanged. See plugins/super-fr/rules/fr-isolation-required.md (#432)."
elif [ -n "${cd_same_repo_worktree:-}" ]; then
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
  # The standard denial. It points at THIS session's workspace first (#432):
  # `fr isolation status` says where it is, `up --branch` makes one when there
  # is none. `down --all` used to be offered here as the no-worktree escape,
  # unconditionally and unqualified — to a session that cannot see the other
  # workspaces it would destroy, uncommitted pre-PR work included. It stays
  # only as an explicitly-warned last resort, after the two remedies that are
  # actually this session's to run. (The orphan heal above is what makes it
  # rarely needed: a session whose own workspace is gone is no longer gated.)
  reason="fr pipeline active — ALL base-repo commands are gated (not just git/gh), so work runs in the isolation worktree. Where is this session's workspace? \`fr isolation status\`. No workspace yet? \`fr isolation up --branch <name>\` (prefix \`FR_ISOLATION_TARGET=worktree\` if this repo has no devcontainer profile). Then run via \`fr isolation exec -- …\`, or lead with \`cd <worktree> && …\` to work from the worktree cwd. Working in a DIFFERENT repo? \`cd <other-repo> && fr isolation up\` is allowed from here — enter that repo's isolation and work from its worktree. LAST RESORT, and rarely right: \`fr isolation down --all\` acts on EVERY workspace in this repo, including other sessions' — a workspace with no PR yet is torn down with whatever was uncommitted in it. \`fr isolation down --all --dry-run\` shows its blast radius first (what it would tear down or keep, and whose sessions are bound), and tearing down another session's workspace needs \`--yes\`. See plugins/super-fr/skills/fr-isolation (exec-bridge discipline, #265/#279/#329/#421/#432)."
fi

jq -n --arg reason "$reason" \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
exit 0
