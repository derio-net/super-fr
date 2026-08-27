#!/bin/bash
# Hermes Agent pre_tool_call hook (terminal|execute_code): block git/gh
# MUTATIONS whose effective cwd is an fr-enabled base clone lacking a valid
# isolation worktree. The Hermes sibling of the Claude fr-isolation-guard.sh,
# but MARKER-based (session-independent) rather than pipeline-sentinel-based:
# Hermes has no Skill-PostToolUse to write a sentinel, so this reuses the shared
# marker decision (fr_isolation_decide_cwd). A discipline backstop, not a
# security boundary. Escapes: `fr isolation …` (never a git/gh mutation, so it
# passes), a leading `cd <worktree>`, and FR_BASE_OK=1.
#
# JSON parsing goes through the shared library (fr_json_field), which resolves
# python3 — or, failing that, jq — from ABSOLUTE paths. The hook never calls a
# bare `jq`: on the Hermes pod the gateway service PATH omits the PVC bin dir
# where jq lives, so a PATH lookup aborted the hook with exit 127 and silently
# disarmed the guard. Every failure mode below is an explicit JSON decision,
# never a bare non-zero exit.

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB="$SCRIPT_DIR/../lib/fr-isolation-decision.sh"

# Deny output must not itself need a JSON encoder: escape with sed (always on
# the base PATH) and keep every reason a single line.
json_escape() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr -d '\n\r'; }
emit_block() { printf '{"decision":"block","reason":"%s"}\n' "$(json_escape "$1")"; }

if [ ! -r "$LIB" ]; then
  emit_block 'fr-isolation guard unavailable: the shared decision library is missing, so the isolation context cannot be established. Refusing terminal/execute_code until the hook install is repaired.'
  exit 0
fi
# shellcheck source=../lib/fr-isolation-decision.sh
. "$LIB"

if ! fr_json_resolve; then
  emit_block 'fr-isolation guard unavailable: no JSON parser (python3 or jq) could be resolved, so the tool payload cannot be read. Refusing terminal/execute_code until the dependency is restored.'
  exit 0
fi

input=$(cat)

tool_name=$(printf '%s' "$input" | fr_json_field tool_name) || tool_name='__HOOK_PARSE_ERROR__'
if [ "$tool_name" = "__HOOK_PARSE_ERROR__" ]; then
  emit_block 'fr-isolation guard: the pre_tool_call payload is not valid JSON, so the isolation context cannot be established. Refusing the call.'
  exit 0
fi

case "$tool_name" in
  terminal | execute_code) ;;
  *) exit 0 ;;
esac

command=$(printf '%s' "$input" | fr_json_field tool_input.command) || command='__HOOK_PARSE_ERROR__'
cwd=$(printf '%s' "$input" | fr_json_field cwd) || cwd='__HOOK_PARSE_ERROR__'
if [ "$command" = "__HOOK_PARSE_ERROR__" ] || [ "$cwd" = "__HOOK_PARSE_ERROR__" ]; then
  emit_block 'fr-isolation guard: the pre_tool_call payload is not valid JSON, so the isolation context cannot be established. Refusing the call.'
  exit 0
fi
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
  emit_block "fr-isolation: git/gh mutation blocked — cwd is an fr-enabled base clone, not an isolation worktree. Enter isolation ('fr isolation up' / fr-goal) and run it from the worktree ('cd <worktree> && …'); or set FR_BASE_OK=1 for a deliberate base-clone command."
fi
exit 0
