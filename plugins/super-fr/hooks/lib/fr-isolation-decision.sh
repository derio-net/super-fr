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

fr_isolation_decide_edit() {
  _fr_file=$1

  # Deliberate base-clone edit — the documented escape hatch.
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

  _fr_toplevel=$(git -C "$_fr_dir" rev-parse --show-toplevel 2>/dev/null) || return 0
  [ -n "$_fr_toplevel" ] || return 0
  _fr_rtop=$(cd "$_fr_toplevel" 2>/dev/null && pwd -P) || return 0

  # fr-enabled? A devcontainer profile (every isolation-capable repo has one) or
  # an fr plans dir. Neither → not our concern, allow.
  _fr_enabled=0
  for _fr_cfg in "$_fr_rtop"/.devcontainer/*/devcontainer.json; do
    [ -f "$_fr_cfg" ] && _fr_enabled=1 && break
  done
  [ -d "$_fr_rtop/docs/superpowers/plans" ] && _fr_enabled=1
  [ "$_fr_enabled" = 1 ] || return 0

  # Valid isolation marker → allow. Valid = present AND recorded toplevel ==
  # current toplevel AND mode == "worktree" AND the toplevel is a LINKED
  # worktree (git-common-dir != git-dir). The linked-worktree check is what
  # defeats a stale marker copied into the primary working tree. Only
  # mode=worktree is honored; unknown modes fail CLOSED (fall through to deny).
  _fr_marker="$_fr_rtop/.fr-isolation"
  if [ -f "$_fr_marker" ]; then
    _fr_recorded=$(jq -r '.toplevel // empty' "$_fr_marker" 2>/dev/null || true)
    _fr_mode=$(jq -r '.mode // "worktree"' "$_fr_marker" 2>/dev/null || echo worktree)
    _fr_rrecorded=""
    [ -n "$_fr_recorded" ] && _fr_rrecorded=$(cd "$_fr_recorded" 2>/dev/null && pwd -P || echo "$_fr_recorded")
    if [ "$_fr_rrecorded" = "$_fr_rtop" ] && [ "$_fr_mode" = "worktree" ]; then
      _fr_common=$(git -C "$_fr_rtop" rev-parse --git-common-dir 2>/dev/null || true)
      _fr_gitdir=$(git -C "$_fr_rtop" rev-parse --git-dir 2>/dev/null || true)
      _fr_rcommon=$(cd "$_fr_rtop" && cd "$_fr_common" 2>/dev/null && pwd -P) || _fr_rcommon="$_fr_common"
      _fr_rgitdir=$(cd "$_fr_rtop" && cd "$_fr_gitdir" 2>/dev/null && pwd -P) || _fr_rgitdir="$_fr_gitdir"
      [ "$_fr_rcommon" != "$_fr_rgitdir" ] && return 0   # a linked worktree → valid
    fi
  fi

  # Operator-managed exemptions: a `.fr-isolation-allow` globlist at the repo
  # root, matched against the file's repo-relative path (bash pattern match —
  # `*` spans `/`, so `projects/**` matches nested paths).
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
