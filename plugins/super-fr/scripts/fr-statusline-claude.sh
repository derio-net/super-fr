#!/bin/bash
# fr-statusline-claude.sh — Claude Code status line on the fr segment (spec 2026-09-14 §5.B).
#
# settings.json:
#   "statusLine": {"type": "command",
#     "command": "bash ~/.claude/plugins/cache/derio-net--super-fr/super-fr/current/scripts/fr-statusline-claude.sh"}
#
# Line 1: model (context size) | ctx:NN% of X | 5h:NN% 7d:NN%   (parts omitted when absent)
# Line 2: branch: <b> | ~/cwd      (branch green when fr, purple when not)
# Line 3: worktree: <path> | no fr-isolation   (same colour)
data=$(cat)

# A real git first on PATH: Apple's /usr/bin/git shim adds ~30 ms per call
# (journal 9ecae0965ac4). Harmless when the path does not exist.
[ -x /Applications/Xcode.app/Contents/Developer/usr/bin/git ] &&
  PATH="/Applications/Xcode.app/Contents/Developer/usr/bin:$PATH"

DIM=$'\033[2m'
BOLD=$'\033[1m'
CYAN=$'\033[36m'
BLUE=$'\033[34m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'
PURPLE=$'\033[35m'
RESET=$'\033[0m'
SEP="${DIM} | ${RESET}"

# The segment lives beside the REAL file, so follow symlinks first (a user may
# link ~/.claude/statusline.sh here). Plain readlink loop: bash 3.2 and older
# macOS have no `readlink -f`.
src="${BASH_SOURCE[0]}"
while [ -L "$src" ]; do
  dir=$(cd -P "$(dirname "$src")" && pwd)
  src=$(readlink "$src")
  case "$src" in /*) ;; *) src="$dir/$src" ;; esac
done
here=$(cd -P "$(dirname "$src")" && pwd)

_pct_color() {
  if [ "$1" -ge 75 ]; then printf '%s' "$RED"
  elif [ "$1" -ge 50 ]; then printf '%s' "$YELLOW"
  else printf '%s' "$GREEN"; fi
}
_size() {
  if [ "$1" -ge 1000000 ]; then printf '%sM' "$(($1 / 1000000))"
  else printf '%sk' "$(($1 / 1000))"; fi
}

model="" size="" used="" five="" seven="" cwd=""
{ IFS= read -r model; IFS= read -r size; IFS= read -r used
  IFS= read -r five; IFS= read -r seven; IFS= read -r cwd; } < <(
  printf '%s' "$data" | jq -r '
    (.model.display_name // "" | sub("^Claude "; "")),
    (.context_window.context_window_size // "" | tostring),
    (.context_window.used_percentage | if type == "number" then floor | tostring else "" end),
    (.rate_limits.five_hour.used_percentage | if type == "number" then floor | tostring else "" end),
    (.rate_limits.seven_day.used_percentage | if type == "number" then floor | tostring else "" end),
    (.workspace.current_dir // .cwd // "")' 2>/dev/null || true
)

line1="${BOLD}${CYAN}${model}${RESET}"
has_size=0
case "$size" in '' | *[!0-9]*) ;; *) [ "$size" -gt 0 ] && has_size=1 ;; esac
[ "$has_size" -eq 1 ] && line1="${line1} ${DIM}($(_size "$size") context)${RESET}"
if [ -n "$used" ]; then
  u=${used%.*}
  ctx="${DIM}ctx:${RESET}$(_pct_color "$u")${u}%${RESET}"
  [ "$has_size" -eq 1 ] && ctx="${ctx}${DIM} of $(_size "$size")${RESET}"
  line1="${line1}${SEP}${ctx}"
fi
rate=""
if [ -n "$five" ]; then
  f=${five%.*}
  rate="${DIM}5h:${RESET}$(_pct_color "$f")${f}%${RESET}"
fi
if [ -n "$seven" ]; then
  s=${seven%.*}
  [ -n "$rate" ] && rate="${rate} "
  rate="${rate}${DIM}7d:${RESET}$(_pct_color "$s")${s}%${RESET}"
fi
[ -n "$rate" ] && line1="${line1}${SEP}${rate}"

rows=$(printf '%s' "$data" | bash "$here/fr-statusline-segment.sh" --format ansi 2>/dev/null)
b_row=$(printf '%s\n' "$rows" | sed -n '1p')
w_row=$(printf '%s\n' "$rows" | sed -n '2p')
# Segment missing or silent: the "none" rows, never a bare separator.
[ -n "$b_row" ] || b_row="${PURPLE}no branch${RESET}"
[ -n "$w_row" ] || w_row="${PURPLE}no fr-isolation${RESET}"

case "$cwd" in
"$HOME" | "$HOME"/*) cwd_short="~${cwd#"$HOME"}" ;;
*) cwd_short="$cwd" ;;
esac
line2="$b_row"
[ -n "$cwd_short" ] && line2="${line2}${SEP}${BLUE}${cwd_short}${RESET}"

printf '%s\n%s\n%s\n' "$line1" "$line2" "$w_row"
