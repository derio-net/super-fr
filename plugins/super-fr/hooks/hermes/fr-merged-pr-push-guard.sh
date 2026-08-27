#!/bin/bash
# Hermes Agent pre_tool_call hook (terminal|execute_code): DENY a `git push`
# when the current branch's PR is MERGED/CLOSED — pushing there orphans the
# commit from `main` (the #320 merge-race). The Hermes sibling of
# fr-merged-pr-push-guard.sh, but MARKER-based rather than sentinel-based:
# scoped to fr-enabled repos so the `gh pr view` call only runs where it's
# relevant. Fail-open on every PR-STATE ambiguity (no push, no PR, gh absent,
# non-fr repo, network/auth error, unparseable gh output) — a discipline
# backstop, not a boundary.
#
# The one case that is NOT a PR-state ambiguity is a broken hook: no JSON parser
# at all, or a payload that is not valid JSON. Those used to abort the script
# with `jq: command not found` (exit 127) because the Hermes gateway service
# PATH omits the PVC bin dir where jq lives. They are now explicit refusals, so
# a disarmed guard is visible instead of silent. `gh` remains this hook's own
# dependency and is deliberately absent from the two isolation hooks.

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB="$SCRIPT_DIR/../lib/fr-isolation-decision.sh"

# Deny output must not itself need a JSON encoder: escape with sed (always on
# the base PATH) and keep every reason a single line.
json_escape() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr -d '\n\r'; }
emit_block() { printf '{"decision":"block","reason":"%s"}\n' "$(json_escape "$1")"; }

if [ ! -r "$LIB" ]; then
  emit_block 'Pre-push guard unavailable: the shared decision library is missing, so a merged-PR push cannot be detected. Refusing the call until the hook install is repaired.'
  exit 0
fi
# shellcheck source=../lib/fr-isolation-decision.sh
. "$LIB"

if ! fr_json_resolve; then
  emit_block 'Pre-push guard unavailable: no JSON parser (python3 or jq) could be resolved, so the tool payload cannot be read. Refusing the call until the dependency is restored.'
  exit 0
fi

input=$(cat)

tool_name=$(printf '%s' "$input" | fr_json_field tool_name) || tool_name='__HOOK_PARSE_ERROR__'
if [ "$tool_name" = "__HOOK_PARSE_ERROR__" ]; then
  emit_block 'Pre-push guard: the pre_tool_call payload is not valid JSON, so a merged-PR push cannot be detected. Refusing the call.'
  exit 0
fi

case "$tool_name" in
  terminal | execute_code) ;;
  *) exit 0 ;;
esac

command=$(printf '%s' "$input" | fr_json_field tool_input.command) || command='__HOOK_PARSE_ERROR__'
if [ "$command" = "__HOOK_PARSE_ERROR__" ]; then
  emit_block 'Pre-push guard: the pre_tool_call payload is not valid JSON, so a merged-PR push cannot be detected. Refusing the call.'
  exit 0
fi

# Act only on a real `git push` subcommand. Mirrors the Claude guard's regex:
# the (^|[^[:alnum:]_]) prefix avoids `mygit push`; global flags may carry a
# bareword value; the trailing anchor catches `git push;` / `git push|tee`
# while rejecting `git pushy` and `--grep=push`.
if ! printf '%s' "$command" | grep -Eq '(^|[^[:alnum:]_])git([[:space:]]+-[^[:space:]]+([[:space:]]+[^[:space:]-][^[:space:]]*)?)*[[:space:]]+push($|[^[:alnum:]_-])'; then
  exit 0
fi

# From here on every exit is FAIL-OPEN: each remaining condition is a genuine
# ambiguity about the PR's state, not a broken guard.
command -v gh >/dev/null 2>&1 || exit 0

cwd=$(printf '%s' "$input" | fr_json_field cwd) || exit 0
case "$cwd" in __HOOK_PARSE_ERROR__ | '') exit 0 ;; esac

# Bound the network call: only resolve PR state inside an fr-enabled repo.
rtop=$(_fr_toplevel_of "$cwd") || exit 0
_fr_is_enabled "$rtop" || exit 0

# Current branch's PR state (checked-out branch — the near-universal push case).
pr_json=$(cd "$cwd" 2>/dev/null && gh pr view --json state 2>/dev/null) || exit 0
[ -n "$pr_json" ] || exit 0
state=$(printf '%s' "$pr_json" | fr_json_field state) || exit 0
case "$state" in __HOOK_PARSE_ERROR__) exit 0 ;; esac

case "$state" in
  MERGED | CLOSED)
    emit_block "Pre-push guard: this branch's PR is $state. Pushing here orphans the commit from 'main' (#320 merge-race). Stop — cherry-pick the commit onto 'main' (or open a fresh branch/PR) instead."
    ;;
esac
exit 0
