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
# JSON parsing is load-bearing (marker parsing). It goes through fr_json_field /
# fr_json_file_field below, which resolve an interpreter from ABSOLUTE paths so
# a stripped service PATH cannot disarm the guards. Callers run under `set -eu`;
# call the decision functions from inside an `if` so a deny (`return 1`) does
# not trip `set -e`.

# --- dependency-free JSON parsing ------------------------------------------
#
# History: these hooks used to shell out to a bare `jq`. On the Hermes agent pod
# jq lives on the PVC under the user's ~/.local/bin, which the gateway service
# PATH omits — every hook invocation died with `jq: command not found` (exit
# 127). Under `set -eu` that aborted the script BEFORE it printed a decision,
# which the harness treats as "no opinion": the guards were silently disarmed.
# A partial repair that added a fail-closed `command -v jq` check then locked
# the agent out of its own terminal, because the same PATH gap still applied and
# the refusal now fired on every call.
#
# The fix is to stop depending on a PATH lookup at all: prefer python3's stdlib
# (present at an absolute path in every environment that runs these hooks) and
# keep a resolved jq as a second, independent parser. A resolution failure is
# reported to the caller, which MUST turn it into an explicit refusal — never a
# silent pass.
#
# Both candidate lists are overridable (space-separated; bare names go through
# PATH, absolute paths are probed directly) for deployments that put the
# interpreter somewhere unusual — and so the no-parser branch stays testable:
#   FR_PYTHON_CANDIDATES, FR_JQ_CANDIDATES

FR_JSON_KIND=""
FR_JSON_BIN=""

: "${FR_PYTHON_CANDIDATES:=python3 /usr/bin/python3 /usr/local/bin/python3 /bin/python3}"
: "${FR_JQ_CANDIDATES:=jq ${HOME:-/nonexistent}/.local/bin/jq /usr/local/bin/jq /usr/bin/jq /opt/homebrew/bin/jq}"

# Probe one candidate; on success set FR_JSON_BIN and return 0.
_fr_try_parser() {
  case "$1" in
    /*)
      [ -x "$1" ] || return 1
      FR_JSON_BIN="$1"
      ;;
    *)
      _fr_res=$(command -v "$1" 2>/dev/null) || return 1
      [ -n "$_fr_res" ] || return 1
      FR_JSON_BIN="$_fr_res"
      ;;
  esac
  return 0
}

# Resolve a JSON parser once. Sets FR_JSON_KIND/FR_JSON_BIN.
#   returns 0 -> a parser is available
#   returns 1 -> no parser at all (caller must refuse explicitly)
fr_json_resolve() {
  [ -n "$FR_JSON_KIND" ] && return 0

  # Word-splitting the candidate lists is intentional.
  # shellcheck disable=SC2086
  for _fr_cand in $FR_PYTHON_CANDIDATES; do
    if _fr_try_parser "$_fr_cand"; then
      FR_JSON_KIND=python3
      return 0
    fi
  done
  # shellcheck disable=SC2086
  for _fr_cand in $FR_JQ_CANDIDATES; do
    if _fr_try_parser "$_fr_cand"; then
      FR_JSON_KIND=jq
      return 0
    fi
  done

  return 1
}

# fr_json_field <dotted.path>
#   JSON document on stdin. Echoes the string value, or "" when the key is
#   absent / null. Echoes the sentinel __HOOK_PARSE_ERROR__ when the document
#   itself is not valid JSON, so a caller can tell "absent" from "malformed".
#   returns 1 only when no parser could be resolved.
fr_json_field() {
  fr_json_resolve || return 1
  if [ "$FR_JSON_KIND" = "python3" ]; then
    # `python3 -c` (NOT a heredoc): stdin must stay free to carry the payload.
    "$FR_JSON_BIN" -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print("__HOOK_PARSE_ERROR__")
    sys.exit(0)
# Every payload this library reads (tool call, marker, `gh --json`) is an
# object. A valid-JSON non-object is still a payload we cannot honor, so it is
# a parse error, not an absent key.
if not isinstance(data, dict):
    print("__HOOK_PARSE_ERROR__")
    sys.exit(0)
for part in sys.argv[1].split("."):
    if not isinstance(data, dict):
        data = ""
        break
    data = data.get(part, "")
print("" if data is None else data)
' "$1"
  else
    if _fr_out=$("$FR_JSON_BIN" -r ".$1 // empty" 2>/dev/null); then
      printf '%s\n' "$_fr_out"
    else
      printf '%s\n' '__HOOK_PARSE_ERROR__'
    fi
  fi
}

# fr_json_file_field <file> <dotted.path> — same, reading a JSON file.
fr_json_file_field() {
  [ -r "$1" ] || { printf '%s\n' '__HOOK_PARSE_ERROR__'; return 0; }
  fr_json_field "$2" < "$1"
}

# --- git resolution --------------------------------------------------------
#
# git is the OTHER load-bearing dependency, and it fails the same silent way:
# `_fr_toplevel_of` cannot distinguish "this is not a git repo" (allow — genuinely
# not our concern) from "git is not runnable here" (every decision degrades to
# allow, i.e. the guard is disarmed). Resolve it from absolute paths for the same
# reason as the JSON parser, and let a hook entrypoint ask explicitly via
# fr_git_resolve so it can refuse instead of silently passing.

FR_GIT_BIN=""
: "${FR_GIT_CANDIDATES:=git /usr/bin/git /usr/local/bin/git /bin/git /opt/homebrew/bin/git}"

# Resolve git once into FR_GIT_BIN.
#   returns 0 -> git is available; 1 -> no usable git
fr_git_resolve() {
  [ -n "$FR_GIT_BIN" ] && return 0
  # Word-splitting the candidate list is intentional.
  # shellcheck disable=SC2086
  for _fr_cand in $FR_GIT_CANDIDATES; do
    case "$_fr_cand" in
      /*)
        [ -x "$_fr_cand" ] || continue
        FR_GIT_BIN="$_fr_cand"
        ;;
      *)
        _fr_res=$(command -v "$_fr_cand" 2>/dev/null) || continue
        [ -n "$_fr_res" ] || continue
        FR_GIT_BIN="$_fr_res"
        ;;
    esac
    return 0
  done
  return 1
}

# --- internal helpers (shared by decide_edit and decide_cwd) ---------------

# Echo the resolved git toplevel for a directory, or return non-zero.
# Returning non-zero when git itself is unavailable preserves the historical
# "treat as not-a-repo" behavior for callers that do not check fr_git_resolve;
# the Hermes entrypoints DO check, and refuse.
_fr_toplevel_of() {
  fr_git_resolve || return 1
  _fr_t=$("$FR_GIT_BIN" -C "$1" rev-parse --show-toplevel 2>/dev/null) || return 1
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
# Any other mode — and any unreadable/unparseable marker, or a missing JSON
# parser — fails CLOSED.
_fr_marker_valid() {
  _fr_rtop=$1
  _fr_marker="$_fr_rtop/.fr-isolation"
  [ -f "$_fr_marker" ] || return 1
  _fr_recorded=$(fr_json_file_field "$_fr_marker" toplevel) || return 1
  _fr_mode=$(fr_json_file_field "$_fr_marker" mode) || return 1
  case "$_fr_recorded" in __HOOK_PARSE_ERROR__) return 1 ;; esac
  case "$_fr_mode" in __HOOK_PARSE_ERROR__) return 1 ;; esac
  [ -n "$_fr_mode" ] || _fr_mode=worktree
  _fr_rrecorded=""
  [ -n "$_fr_recorded" ] && _fr_rrecorded=$(cd "$_fr_recorded" 2>/dev/null && pwd -P || echo "$_fr_recorded")
  [ "$_fr_rrecorded" = "$_fr_rtop" ] || return 1
  case "$_fr_mode" in
    worktree)
      fr_git_resolve || return 1
      _fr_common=$("$FR_GIT_BIN" -C "$_fr_rtop" rev-parse --git-common-dir 2>/dev/null || true)
      _fr_gitdir=$("$FR_GIT_BIN" -C "$_fr_rtop" rev-parse --git-dir 2>/dev/null || true)
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

# fr_isolation_marker_valid <dir>
#   0 -> dir's git toplevel IS a genuine fr isolation workspace (valid marker)
#   1 -> it is not (plain repo, base clone, non-repo, stale/forged marker)
#
# A stricter question than fr_isolation_decide_cwd, and a different one.
# decide_cwd asks "is THIS repo's own isolation being violated?" and so answers
# 0 for a non-fr repo — correct for the edit gate, which has no business in a
# repo that never opted into fr. But the bash guard's cross-repo hop asks
# "is this a legitimate DESTINATION while a pipeline is live?", and "any repo
# that never opted into fr" is far too broad an answer: `$HOME` is a git repo on
# any machine with a dotfiles repo, which would put `~/.ssh` one `cd` away.
# Used by the Claude bash guard (super-fr#421).
fr_isolation_marker_valid() {
  [ -d "$1" ] || return 1
  _fr_rtop=$(_fr_toplevel_of "$1") || return 1
  _fr_marker_valid "$_fr_rtop"
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
