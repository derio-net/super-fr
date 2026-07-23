#!/bin/bash
# Hermes Agent pre_tool_call hook (terminal|execute_code): block git/gh
# MUTATIONS whose effective cwd is an fr-enabled base clone lacking a valid
# isolation worktree. The Hermes sibling of the Claude fr-isolation-guard.sh,
# but MARKER-based (session-independent) rather than pipeline-sentinel-based:
# Hermes has no Skill-PostToolUse to write a sentinel, so this reuses the shared
# marker decision (fr_isolation_decide_cwd). A discipline backstop, not a
# security boundary. Escapes: `fr isolation …` (never a git/gh mutation, so it
# passes), a leading `cd <worktree>`, and FR_BASE_OK=1.

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
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
[ -n "$command" ] || exit 0

# Effective directory: a leading `cd <target> [&& | ;]` is the documented way to
# move into the worktree before git/gh ops, so evaluate the command against its
# target, not the (pre-cd) payload cwd. Otherwise use the payload cwd.
effective_dir="$cwd"
cd_target=$(printf '%s' "$command" | sed -nE 's/^[[:space:]]*cd[[:space:]]+("([^"]+)"|'\''([^'\'']+)'\''|([^[:space:];&|]+)).*/\2\3\4/p')
if [ -n "$cd_target" ]; then
  case "$cd_target" in "~"*) cd_target="$HOME${cd_target#\~}" ;; esac
  if rtarget=$(cd "$cd_target" 2>/dev/null && pwd -P); then
    effective_dir="$rtarget"
  fi
fi

[ -n "$effective_dir" ] || exit 0

# Allowed context (worktree / non-fr repo / FR_BASE_OK) → never our concern.
if fr_isolation_decide_cwd "$effective_dir"; then
  exit 0
fi

# Blocked context: only git/gh MUTATIONS are denied; read-only / unknown
# commands pass (this is a discipline backstop, not an allowlist firewall).
is_mutation() {
  printf '%s' "$1" | grep -Eq \
    '(^|[;&|[:space:]])git[[:space:]]+(commit|push|merge|rebase|reset|checkout|switch|add|rm|mv|restore|stash|tag|cherry-pick|revert|apply|am|clean|pull)([[:space:]]|$)' &&
    return 0
  printf '%s' "$1" | grep -Eq \
    '(^|[;&|[:space:]])gh[[:space:]]+(pr|issue|release|repo)[[:space:]]+(create|merge|edit|close|delete|comment|ready|review)([[:space:]]|$)' &&
    return 0
  return 1
}

if is_mutation "$command"; then
  jq -n --arg reason "fr-isolation: git/gh mutation blocked — cwd is an fr-enabled base clone, not an isolation worktree. Enter isolation (\`fr isolation up\` / fr-goal) and run it from the worktree (\`cd <worktree> && …\`); or set FR_BASE_OK=1 for a deliberate base-clone command." \
    '{decision: "block", reason: $reason}'
fi
exit 0
