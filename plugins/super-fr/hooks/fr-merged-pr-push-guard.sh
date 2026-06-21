#!/bin/bash
# PreToolUse(Bash) hook: while an fr pipeline is active (session sentinel
# present, written by fr-pipeline-sentinel.sh), DENY a `git push` when the
# current branch's PR is MERGED/CLOSED — pushing there orphans the commit from
# `main` (the #320 merge-race).
#
# Fail-open on EVERY ambiguity (no sentinel, no push in the command, no PR for
# the branch, gh/jq absent, network/auth error): this is a discipline backstop,
# not a security boundary. Companion to fr-isolation-guard.sh.

set -eu

input=$(cat)

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')
[ "$tool_name" = "Bash" ] || exit 0

session_id=$(printf '%s' "$input" | jq -r '.session_id // empty')
[ -n "$session_id" ] || exit 0

dir="${FR_SENTINEL_DIR:-$HOME/.cache/fr/sentinels}"
sentinel="$dir/$session_id.json"
[ -f "$sentinel" ] || exit 0   # no active pipeline for this session

command=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')

# Act only on a real `git push` subcommand. The (^|[^[:alnum:]_]) prefix avoids
# matching `mygit push`. Each global flag may carry an optional bareword value,
# so `git -C <dir> push`, `git -c k=v push`, and `git push --force…` all match.
# The trailing ($|[^[:alnum:]_-]) anchor catches metachar terminators
# (`git push;`, `git push|tee`) while still rejecting `git pushy` and
# `git push-foo`; requiring whitespace before `push` avoids `--grep=push` /
# commit-message false positives.
if ! printf '%s' "$command" | grep -Eq '(^|[^[:alnum:]_])git([[:space:]]+-[^[:space:]]+([[:space:]]+[^[:space:]-][^[:space:]]*)?)*[[:space:]]+push($|[^[:alnum:]_-])'; then
  exit 0
fi

# Need gh + jq to resolve PR state; absent → fail-open.
command -v gh >/dev/null 2>&1 || exit 0
command -v jq >/dev/null 2>&1 || exit 0

cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
[ -n "$cwd" ] || exit 0

# Current branch's PR state, read from the command's cwd (the worktree). No PR
# for the branch / gh error / network failure → fail-open. Checks the
# CHECKED-OUT branch (the near-universal push case); an explicit
# `git push origin HEAD:other` is out of scope.
pr_json=$(cd "$cwd" 2>/dev/null && gh pr view --json state 2>/dev/null) || exit 0
[ -n "$pr_json" ] || exit 0
state=$(printf '%s' "$pr_json" | jq -r '.state // empty' 2>/dev/null) || exit 0

case "$state" in
  MERGED|CLOSED)
    jq -n --arg reason "Pre-push guard: this branch's PR is $state. Pushing here orphans the commit from \`main\` (#320 merge-race). Stop — cherry-pick the commit onto \`main\` (or open a fresh branch/PR) instead. See plugins/super-fr/skills/fr-isolation (pre-push guard)." \
      '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
    exit 0
    ;;
esac
exit 0
