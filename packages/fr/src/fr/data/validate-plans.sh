#!/usr/bin/env bash
# Canonical plan validator — profile-driven.
# Ships with super-fr plugin. Per-repo thin wrappers call this.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ERRORS=()
PROFILE=""

# Artifact directories come from the path resolver (`fr settings paths --shell --no-create`,
# spec 2026-11-04 R1), so they follow the repo's placement; the literals below are the
# `repo` layout's own and the fallback. `--no-create` keeps the read side-effect free: under
# quiet it never creates the `fr` branch or worktree (review pr1431-r7).
#
# `fr` is resolved as the hooks resolve it (fr-isolation-decision.sh `fr_fr_resolve`): an
# absolute FR_HARNESS_FR naming an executable file, else the first ABSOLUTE PATH entry
# holding one. A relative PATH entry would run whatever `fr` sits in the checkout.
#
# Only an explicit placement refusal is fatal: exit 2 with stderr starting
# `fr settings paths: refused: ` (fr.commands.settings_cmd.PATHS_REFUSAL_PREFIX); falling
# back then would validate the wrong directory. Every other failure (no `fr`, a broken or
# too-old one, a binary-identity refusal, a usage error) validates the literals as before.
# The answer is read by name and never eval'd. `fr`'s toplevel prefers $FR_REPO_ROOT, so it
# is unset for the call and `fr` runs from $REPO_ROOT, the toplevel this script uses.
FR_BIN=""
case "${FR_HARNESS_FR:-}" in
  /*) if [ -f "$FR_HARNESS_FR" ] && [ -x "$FR_HARNESS_FR" ]; then FR_BIN="$FR_HARNESS_FR"; fi ;;
esac
if [ -z "$FR_BIN" ]; then
  _fr_rest="${PATH:-}:"
  while [ -n "$_fr_rest" ]; do
    _fr_dir="${_fr_rest%%:*}"
    _fr_rest="${_fr_rest#*:}"
    case "$_fr_dir" in /*) ;; *) continue ;; esac
    if [ -f "$_fr_dir/fr" ] && [ -x "$_fr_dir/fr" ]; then
      FR_BIN="$_fr_dir/fr"
      break
    fi
  done
fi
# _fr_answer <KEY>: one key of the `--shell` answer, unquoted; empty unless it is a plain
# absolute path (shlex leaves one bare or wraps it in single quotes, nothing else).
_fr_answer() {
  local v
  v="$(printf '%s\n' "$FR_PATHS" | sed -n "s/^$1=//p" | head -n 1)"
  case "$v" in \'*\') v="${v#\'}"; v="${v%\'}" ;; esac
  case "$v" in /*) ;; *) return 0 ;; esac
  case "$v" in *\'*) return 0 ;; esac
  printf '%s' "$v"
}
FR_PATHS=""
if [ -n "$FR_BIN" ]; then
  FR_ERR="$(mktemp)"
  _fr_rc=0
  FR_PATHS="$(cd "$REPO_ROOT" && env -u FR_REPO_ROOT "$FR_BIN" settings paths --shell --no-create 2>"$FR_ERR")" || _fr_rc=$?
  if [ "$_fr_rc" -ne 0 ]; then
    FR_PATHS=""
    if [ "$_fr_rc" -eq 2 ] && head -n 1 "$FR_ERR" | grep -q '^fr settings paths: refused: '; then
      cat "$FR_ERR" >&2
      rm -f "$FR_ERR"
      exit 2
    fi
  fi
  rm -f "$FR_ERR"
fi
for _fr_key in FR_PLAN_CONFIG_FILE FR_PLANS_DIR FR_ARCHIVED_PLANS_DIR FR_LEGACY_ARCHIVED_PLANS_DIR; do
  _fr_val="$(_fr_answer "$_fr_key")"
  if [ -n "$_fr_val" ]; then printf -v "$_fr_key" '%s' "$_fr_val"; fi
done
: "${FR_PLAN_CONFIG_FILE:=$REPO_ROOT/docs/superpowers/plan-config.yaml}"
: "${FR_PLANS_DIR:=$REPO_ROOT/docs/superpowers/plans}"
: "${FR_ARCHIVED_PLANS_DIR:=$REPO_ROOT/docs/superpowers/implemented/plans}"
: "${FR_LEGACY_ARCHIVED_PLANS_DIR:=$REPO_ROOT/docs/superpowers/archived-plans}"

FILES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    *) FILES+=("$1"); shift ;;
  esac
done

if [ -z "$PROFILE" ]; then
  PROFILE="$FR_PLAN_CONFIG_FILE"
fi

if [ -f "$PROFILE" ]; then
  FILENAME_PATTERN=$(sed -n '/^plan:/,/^[^ ]/{ s/^  filename: *"\(.*\)"/\1/p }' "$PROFILE" | head -1)
  REQUIRED_HEADERS=$(sed -n '/^header:/,/^[^ ]/{/^  required:/,/^  [^ ]/{/^    - /{ s/^    - //p }}}' "$PROFILE")
  STATUS_VALUES=$(sed -n '/^header:/,/^[^ ]/{/status_values:/,/^  [^ ]/{/^    - /{ s/^    - //p }}}' "$PROFILE")
else
  FILENAME_PATTERN="YYYY-MM-DD-{name}.md"
  REQUIRED_HEADERS="Status"
  STATUS_VALUES=""
fi

if ! echo "$REQUIRED_HEADERS" | grep -q "Status"; then
  REQUIRED_HEADERS="$REQUIRED_HEADERS
Status"
fi

validate_file() {
  local f="$1"
  local base
  base="$(basename "$f" .md)"

  # Filename validation
  case "$FILENAME_PATTERN" in
    *"{layer}"*)
      if ! [[ "$base" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}--[a-z]+--[a-z0-9].*$ ]]; then
        ERRORS+=("$base: malformed filename (expected YYYY-MM-DD--<layer>--<details>)")
      fi
      ;;
    *)
      if ! [[ "$base" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9].*$ ]]; then
        ERRORS+=("$base: malformed filename (expected YYYY-MM-DD-<name>)")
      fi
      ;;
  esac

  # Header validation
  local header
  header=$(head -20 "$f")

  while IFS= read -r field; do
    [ -z "$field" ] && continue
    if ! echo "$header" | grep -q "\*\*${field}:\*\*"; then
      ERRORS+=("$base: missing **${field}:** line in header")
    fi
  done <<< "$REQUIRED_HEADERS"

  # Spec reference validation
  if echo "$REQUIRED_HEADERS" | grep -q "Spec"; then
    if echo "$header" | grep -q '\*\*Spec:\*\*'; then
      local spec_ref
      spec_ref=$(echo "$header" | sed -n 's/.*\*\*Spec:\*\* `\([^`]*\)`.*/\1/p' | head -1)
      if [ -z "$spec_ref" ]; then
        ERRORS+=("$base: **Spec:** line has no backtick-enclosed path")
      elif [ "$spec_ref" != "none" ] && [[ "$spec_ref" != willikins/* ]] && [[ "$spec_ref" != frank/* ]] && [[ "$spec_ref" != content-factory/* ]]; then
        if [ ! -f "$REPO_ROOT/$spec_ref" ]; then
          ERRORS+=("$base: spec ref not found: $spec_ref")
        fi
      fi
    fi
  fi

  # Status value validation
  if [ -n "$STATUS_VALUES" ]; then
    local status_val
    status_val=$(echo "$header" | sed -n 's/.*\*\*Status:\*\* \(.*\)/\1/p' | head -1)
    status_val="${status_val%% (*}"
    status_val="${status_val#semi-}"
    if [ -n "$status_val" ] && ! echo "$STATUS_VALUES" | grep -qx "$status_val"; then
      ERRORS+=("$base: invalid status '$status_val' — allowed: $(echo "$STATUS_VALUES" | tr '\n' ', ')")
    fi
  fi

  # Structure validation
  local has_phases=false
  if grep -q '^## Phase [0-9]' "$f"; then
    has_phases=true
  fi

  if $has_phases; then
    while IFS= read -r line; do
      if ! [[ "$line" =~ \[(manual|agentic)\] ]]; then
        ERRORS+=("$base: untagged phase: $line")
      fi
    done < <(grep '^## Phase [0-9]' "$f")

    if grep -q '^## Task [0-9]' "$f"; then
      ERRORS+=("$base: uses '## Task' — should be '### Task' (h3 inside Phase)")
    fi
  else
    if grep -q '^## Task [0-9]' "$f"; then
      ERRORS+=("$base: uses '## Task' — should be '### Task'")
    fi
  fi
}

if [ ${#FILES[@]} -gt 0 ]; then
  for f in "${FILES[@]}"; do
    [ -f "$f" ] && validate_file "$f"
  done
else
  PLANS_DIR="$FR_PLANS_DIR"
  # Canonical archive (2026-06-05 spec) + legacy fallback for unmigrated repos.
  IMPLEMENTED_DIR="$FR_ARCHIVED_PLANS_DIR"
  LEGACY_ARCHIVE_DIR="$FR_LEGACY_ARCHIVED_PLANS_DIR"
  for f in "$PLANS_DIR"/*.md "$IMPLEMENTED_DIR"/*.md "$LEGACY_ARCHIVE_DIR"/*.md; do
    [ -e "$f" ] && validate_file "$f"
  done
fi

if [ ${#ERRORS[@]} -gt 0 ]; then
  echo "Plan validation failed:" >&2
  for e in "${ERRORS[@]}"; do
    echo "  - $e" >&2
  done
  exit 1
fi
