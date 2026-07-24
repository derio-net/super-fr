#!/bin/bash
# Pure fr-isolation edit decision — no stdin/stdout protocol, no tool-name
# gating, no harness-specific deny shape. The caller (a per-harness hook
# entrypoint) parses its own tool payload, extracts the target file path, and
# formats its own deny output. This library answers only one question: given an
# absolute target path, should an edit be BLOCKED in the current fr-isolation
# context?
#
#   fr_isolation_decide_edit <file>
#     returns 0  -> ALLOW (edit may proceed)
#     returns 1  -> BLOCK (edit is outside a valid fr-isolation workspace)
#
# Honors FR_BASE_OK=1 and a `.fr-isolation-allow` globlist at the repo root.
# Shared by the Claude Code PreToolUse hook (plugins/super-fr/hooks/
# fr-isolation-required.sh) and the Hermes pre_tool_call hook
# (plugins/super-fr/hooks/hermes/fr-isolation-required.sh) so the marker /
# allowlist / fr-enabled logic lives in exactly one tested place.
#
# jq is load-bearing (marker parsing). Callers run under `set -eu`; call this
# function from inside an `if` so a deny (`return 1`) does not trip `set -e`.

# --- internal helpers (shared by decide_edit and decide_cwd) ---------------

# Echo the resolved git toplevel for a directory, or return non-zero.
_fr_toplevel_of() {
  _fr_t=$(git -C "$1" rev-parse --show-toplevel 2>/dev/null) || return 1
  [ -n "$_fr_t" ] || return 1
  (cd "$_fr_t" 2>/dev/null && pwd -P) || return 1
}

# Return 0 if the given resolved toplevel is fr-enabled (devcontainer profile or
# an fr plans dir), else 1.
_fr_is_enabled() {
  for _fr_cfg in "$1"/.devcontainer/*/devcontainer.json; do
    [ -f "$_fr_cfg" ] && return 0
  done
  [ -d "$1/docs/superpowers/plans" ] && return 0
  return 1
}

# Return 0 if the toplevel carries a VALID isolation marker. Both modes require
# recorded toplevel == current toplevel (defeats a marker copied elsewhere).
# Then the mode branch:
#   worktree — the toplevel must be a LINKED worktree (git-common-dir !=
#     git-dir); this defeats a stale marker copied into the primary tree.
#   external — a preparer's claim over its own checkout: require live container
#     evidence (/.dockerenv, /run/.containerenv, or $KUBERNETES_SERVICE_HOST),
#     so a marker forged on a bare host never validates.
# Any other mode fails CLOSED.
_fr_marker_valid() {
  _fr_rtop=$1
  _fr_marker="$_fr_rtop/.fr-isolation"
  [ -f "$_fr_marker" ] || return 1
  _fr_recorded=$(jq -r '.toplevel // empty' "$_fr_marker" 2>/dev/null || true)
  _fr_mode=$(jq -r '.mode // "worktree"' "$_fr_marker" 2>/dev/null || echo worktree)
  _fr_rrecorded=""
  [ -n "$_fr_recorded" ] && _fr_rrecorded=$(cd "$_fr_recorded" 2>/dev/null && pwd -P || echo "$_fr_recorded")
  [ "$_fr_rrecorded" = "$_fr_rtop" ] || return 1
  case "$_fr_mode" in
    worktree)
      _fr_common=$(git -C "$_fr_rtop" rev-parse --git-common-dir 2>/dev/null || true)
      _fr_gitdir=$(git -C "$_fr_rtop" rev-parse --git-dir 2>/dev/null || true)
      _fr_rcommon=$(cd "$_fr_rtop" && cd "$_fr_common" 2>/dev/null && pwd -P) || _fr_rcommon="$_fr_common"
      _fr_rgitdir=$(cd "$_fr_rtop" && cd "$_fr_gitdir" 2>/dev/null && pwd -P) || _fr_rgitdir="$_fr_gitdir"
      [ "$_fr_rcommon" != "$_fr_rgitdir" ]
      ;;
    external)
      [ -f /.dockerenv ] || [ -f /run/.containerenv ] || [ -n "${KUBERNETES_SERVICE_HOST:-}" ]
      ;;
    *)
      return 1
      ;;
  esac
}

# --- public decisions ------------------------------------------------------

# fr_isolation_decide_cwd <dir>
#   0 -> ALLOWED context (dir is a worktree, a non-fr repo, or outside any repo)
#   1 -> BLOCKED context (dir is an fr-enabled base clone with no valid marker)
# Honors FR_BASE_OK=1. Used by both the edit gate and the bash guard.
fr_isolation_decide_cwd() {
  [ "${FR_BASE_OK:-}" = "1" ] && return 0
  [ -d "$1" ] || return 0
  _fr_rtop=$(_fr_toplevel_of "$1") || return 0
  _fr_is_enabled "$_fr_rtop" || return 0
  _fr_marker_valid "$_fr_rtop" && return 0
  return 1
}

# fr_isolation_decide_edit <file>
#   0 -> ALLOW the edit; 1 -> BLOCK it.
# An fr-enabled base-clone edit is blocked unless `.fr-isolation-allow` exempts
# the specific repo-relative path.
fr_isolation_decide_edit() {
  _fr_file=$1

  [ "${FR_BASE_OK:-}" = "1" ] && return 0
  [ -n "$_fr_file" ] || return 0   # no parseable target — not a decision
  # An absolute path is required; a relative one would resolve the toplevel
  # against the wrong (session-cwd) repo.
  case "$_fr_file" in /*) ;; *) return 0 ;; esac

  # Nearest existing ancestor dir (a write may target a not-yet-created file).
  _fr_dir=$(dirname "$_fr_file")
  while [ ! -d "$_fr_dir" ] && [ "$_fr_dir" != "/" ] && [ "$_fr_dir" != "." ]; do
    _fr_dir=$(dirname "$_fr_dir")
  done
  [ -d "$_fr_dir" ] || return 0

  # Allowed context (worktree / non-fr / FR_BASE_OK) → allow the edit.
  if fr_isolation_decide_cwd "$_fr_dir"; then
    return 0
  fi

  # Blocked context — but `.fr-isolation-allow` can exempt specific paths.
  _fr_rtop=$(_fr_toplevel_of "$_fr_dir") || return 1
  _fr_allow="$_fr_rtop/.fr-isolation-allow"
  if [ -f "$_fr_allow" ]; then
    _fr_rdir=$(cd "$_fr_dir" 2>/dev/null && pwd -P) || _fr_rdir="$_fr_dir"
    _fr_rfile="$_fr_rdir${_fr_file#"$_fr_dir"}"
    _fr_rel=""
    case "$_fr_rfile" in "$_fr_rtop"/*) _fr_rel=${_fr_rfile#"$_fr_rtop"/} ;; esac
    if [ -n "$_fr_rel" ]; then
      while IFS= read -r _fr_pattern || [ -n "$_fr_pattern" ]; do
        [ -n "$_fr_pattern" ] || continue
        case "$_fr_pattern" in \#*) continue ;; esac
        # Glob match is intentional: the allowlist pattern (e.g. projects/**)
        # must expand, so the RHS is deliberately unquoted.
        # shellcheck disable=SC2053,SC2254
        if [[ "$_fr_rel" == $_fr_pattern ]]; then return 0; fi
      done < "$_fr_allow"
    fi
  fi

  return 1   # nothing allowed it → BLOCK
}
