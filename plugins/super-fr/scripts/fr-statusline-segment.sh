#!/bin/bash
# fr-statusline-segment.sh — session branch + fr-isolation rows (spec 2026-09-14 §5.A).
#
# Answers two questions for a status line: which branch is this session
# working on, and is it inside an fr-isolation workspace?
#
# Input:  Claude Code status-line JSON on stdin ({session_id,
#         workspace.current_dir, cwd}), or --cwd <dir> (stdin is NOT read).
# Output: --format plain (default) — exactly three lines:
#           fr | none
#           branch: <b> | no branch
#           worktree: <abs path> | no fr-isolation
#         --format ansi — the two rows, green when fr, purple when not.
#         --format oneline — "fr:<branch>" | "<branch>" (Hermes 40-char slot).
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

# (resolution rules: phase 2)

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
