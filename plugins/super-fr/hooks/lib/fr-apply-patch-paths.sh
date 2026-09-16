#!/bin/bash
# Extract every target path from a Codex apply_patch payload, and
# resolve a path against a payload cwd.
#
# Codex reports file edits as tool_name "apply_patch" with the patch
# text in tool_input.command (learn.chatgpt.com/docs/hooks). The body
# names its targets on `*** <verb>:` lines and carries MULTIPLE files
# per call. This library is the only Codex-specific parsing in the
# enforcement path; the allow/deny decision itself stays in
# lib/fr-isolation-decision.sh, shared with Claude, Hermes and OpenCode.

# fr_apply_patch_paths <patch-text>
#   Echoes one repo-relative path per line, in payload order.
#   Anchored at column 0 so patch-like prose cannot inject a path.
fr_apply_patch_paths() {
  printf '%s\n' "$1" | sed -nE \
    's/^\*\*\*[[:space:]]+(Add File|Update File|Delete File|Move to):[[:space:]]*(.+)$/\2/p' \
    | sed -e 's/[[:space:]]*$//' -e '/^$/d'
}

# fr_resolve_against <cwd> <path>
#   Absolute path stays; a relative one is joined onto cwd. See the
#   decision library: fr_isolation_decide_edit ALLOWS any non-absolute
#   path by design, so an unresolved relative path silently disarms
#   the gate. Never call the decision library without this.
fr_resolve_against() {
  case "$2" in
    /*) printf '%s\n' "$2" ;;
    *)  printf '%s\n' "${1%/}/$2" ;;
  esac
}
