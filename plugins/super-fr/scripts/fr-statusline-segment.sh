#!/bin/bash
# fr-statusline-segment.sh — session branch + fr-isolation rows (spec 2026-09-14 §5.A).
#
# Answers two questions for a status line: which branch is this session
# working on, and is it inside an fr-isolation workspace?
#
# Input:  Claude Code status-line JSON on stdin ({session_id,
#         workspace.current_dir, cwd}), or --cwd <dir> (stdin is NOT read,
#         so there is no session id and rule 1 never fires).
#
# Resolution (first match wins):
#   1. Bound. The session id is set (a path-like id is dropped), the index
#      file $FR_SESSIONS_DIR/<id>.json exists, and its worktree is non-empty
#      and exists: state fr, branch = index branch, worktree = index
#      worktree. A binding whose worktree is gone is stale and ignored.
#   2. cwd in a repo. One `git rev-parse --path-format=absolute` call gives
#      the toplevel, the common dir and HEAD. HEAD refs/heads/<b> gives the
#      branch; a detached or unborn HEAD gives no branch. State fr only when
#      a <common>/fr/isolation/*.json state file names a worktree whose
#      physical path equals the toplevel; then worktree = the toplevel.
#   Otherwise (no repo, no cwd, bad JSON): the "none" rows.
#
# Output: --format plain (default) — exactly three lines:
#           line 1: state — "fr" or "none"
#           line 2: "branch: <b>" or "no branch"
#           line 3: "worktree: <abs path>" or "no fr-isolation"
#         --format ansi — lines 2-3 only, green when fr, purple when none.
#         --format oneline — "fr:<branch>" when fr, else "<branch>"
#           ("no branch" spelled out); no ANSI (Hermes 40-char slot).
#         Any other --format value falls back to plain.
#
# Env: FR_SESSIONS_DIR (default ~/.cache/fr/sessions) — per-session index.
#
# Shell + jq + git only. NEVER the fr CLI (4 s). Every failure path
# degrades to the "none" rows and exit 0 — a status line must never break
# the harness.
set -u

format=plain
cwd=""
cwd_given=0
while [ $# -gt 0 ]; do
  case "$1" in
  --format) format="${2:-}"; shift; [ $# -gt 0 ] && shift ;;
  --format=*) format="${1#--format=}"; shift ;;
  --cwd) cwd="${2:-}"; cwd_given=1; shift; [ $# -gt 0 ] && shift ;;
  --cwd=*) cwd="${1#--cwd=}"; cwd_given=1; shift ;;
  *) shift ;;
  esac
done
case "$format" in plain | ansi | oneline) ;; *) format=plain ;; esac

session_id=""
if [ "$cwd_given" -eq 0 ]; then
  { IFS= read -r session_id; IFS= read -r cwd; } < <(
    jq -r '(.session_id // ""), (.workspace.current_dir // .cwd // "")' 2>/dev/null || true
  )
fi

state=none
branch=""
worktree=""

sessions_dir="${FR_SESSIONS_DIR:-$HOME/.cache/fr/sessions}"
case "$session_id" in */* | .*) session_id="" ;; esac

# 1. Bound session: one index read; a binding whose worktree is gone is stale.
if [ -n "$session_id" ] && [ -f "$sessions_dir/$session_id.json" ]; then
  b_branch=""
  b_wt=""
  { IFS= read -r b_branch; IFS= read -r b_wt; } < <(
    jq -r '(.branch // ""), (.worktree // "")' "$sessions_dir/$session_id.json" 2>/dev/null || true
  )
  if [ -n "$b_wt" ] && [ -d "$b_wt" ]; then
    state=fr
    branch="$b_branch"
    worktree="$b_wt"
  fi
fi

# 2. cwd in a repo: one git call (absolute paths, so a subdirectory cwd works).
if [ "$state" = none ] && [ -n "${cwd:-}" ] && [ -d "$cwd" ]; then
  toplevel=""
  common=""
  head=""
  { IFS= read -r toplevel; IFS= read -r common; IFS= read -r head; } < <(
    git -C "$cwd" --no-optional-locks rev-parse --path-format=absolute \
      --show-toplevel --git-common-dir --symbolic-full-name HEAD 2>/dev/null || true
  )
  if [ -n "$toplevel" ] && [ -n "$common" ]; then
    # refs/heads/<b> is a branch; "HEAD" is detached (or unborn) -> no branch.
    case "$head" in refs/heads/?*) branch="${head#refs/heads/}" ;; esac
    if [ -d "$common/fr/isolation" ]; then
      # One jq over every workspace state file; compare physical paths.
      while IFS= read -r wt; do
        [ -n "$wt" ] && [ -d "$wt" ] || continue
        if [ "$(cd "$wt" 2>/dev/null && pwd -P)" = "$toplevel" ]; then
          state=fr
          worktree="$toplevel"
          break
        fi
      done < <(jq -rn 'inputs.worktree // empty' "$common"/fr/isolation/*.json 2>/dev/null || true)
    fi
  fi
fi

if [ -n "$branch" ]; then b_row="branch: $branch"; else b_row="no branch"; fi
if [ "$state" = fr ]; then w_row="worktree: $worktree"; else w_row="no fr-isolation"; fi

case "$format" in
plain) printf '%s\n%s\n%s\n' "$state" "$b_row" "$w_row" ;;
ansi)
  if [ "$state" = fr ]; then c=$'\033[32m'; else c=$'\033[35m'; fi
  r=$'\033[0m'
  printf '%s%s%s\n%s%s%s\n' "$c" "$b_row" "$r" "$c" "$w_row" "$r"
  ;;
oneline)
  b="${branch:-no branch}"
  if [ "$state" = fr ]; then printf 'fr:%s\n' "$b"; else printf '%s\n' "$b"; fi
  ;;
esac
exit 0
