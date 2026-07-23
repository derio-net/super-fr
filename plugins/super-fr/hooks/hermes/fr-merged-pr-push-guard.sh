#!/bin/bash
# Hermes Agent pre_tool_call hook (terminal|execute_code): DENY a `git push`
# when the current branch's PR is MERGED/CLOSED — pushing there orphans the
# commit from `main` (the #320 merge-race). The Hermes sibling of
# fr-merged-pr-push-guard.sh, but MARKER-based rather than sentinel-based:
# scoped to fr-enabled repos so the `gh pr view` call only runs where it's
# relevant. Fail-open on EVERY ambiguity (no push, no PR, gh/jq absent,
# non-fr repo, network/auth error) — a discipline backstop, not a boundary.

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../lib/fr-isolation-decision.sh
. "$SCRIPT_DIR/../lib/fr-isolation-decision.sh"

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')
case "$tool_name" in
  terminal | execute_code) ;;
  *) exit 0 ;;
esac

command=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')

# Act only on a real `git push` subcommand. Mirrors the Claude guard's regex:
# the (^|[^[:alnum:]_]) prefix avoids `mygit push`; global flags may carry a
# bareword value; the trailing anchor catches `git push;` / `git push|tee`
# while rejecting `git pushy` and `--grep=push`.
if ! printf '%s' "$command" | grep -Eq '(^|[^[:alnum:]_])git([[:space:]]+-[^[:space:]]+([[:space:]]+[^[:space:]-][^[:space:]]*)?)*[[:space:]]+push($|[^[:alnum:]_-])'; then
  exit 0
fi

command -v gh >/dev/null 2>&1 || exit 0
command -v jq >/dev/null 2>&1 || exit 0

cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
[ -n "$cwd" ] || exit 0

# Bound the network call: only resolve PR state inside an fr-enabled repo.
rtop=$(_fr_toplevel_of "$cwd") || exit 0
_fr_is_enabled "$rtop" || exit 0

# Current branch's PR state (checked-out branch — the near-universal push case).
pr_json=$(cd "$cwd" 2>/dev/null && gh pr view --json state 2>/dev/null) || exit 0
[ -n "$pr_json" ] || exit 0
state=$(printf '%s' "$pr_json" | jq -r '.state // empty' 2>/dev/null) || exit 0

case "$state" in
  MERGED | CLOSED)
    jq -n --arg reason "Pre-push guard: this branch's PR is $state. Pushing here orphans the commit from \`main\` (#320 merge-race). Stop — cherry-pick the commit onto \`main\` (or open a fresh branch/PR) instead." \
      '{decision: "block", reason: $reason}'
    ;;
esac
exit 0
