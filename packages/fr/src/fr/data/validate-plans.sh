#!/usr/bin/env bash
# Canonical plan validator — profile-driven.
# Ships with super-fr plugin. Per-repo thin wrappers call this.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ERRORS=()
PROFILE=""

FILES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    *) FILES+=("$1"); shift ;;
  esac
done

if [ -z "$PROFILE" ]; then
  PROFILE="$REPO_ROOT/docs/superpowers/plan-config.yaml"
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
  PLANS_DIR="$REPO_ROOT/docs/superpowers/plans"
  # Canonical archive (2026-06-05 spec) + legacy fallback for unmigrated repos.
  IMPLEMENTED_DIR="$REPO_ROOT/docs/superpowers/implemented/plans"
  LEGACY_ARCHIVE_DIR="$REPO_ROOT/docs/superpowers/archived-plans"
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
