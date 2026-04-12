#!/usr/bin/env bash
# Audit all repos in a workspace for superpowers config state.
# Usage: audit-repos.sh <workspace-dir>

set -euo pipefail

WORKSPACE="${1:?Usage: audit-repos.sh <workspace-dir>}"

if [ ! -d "$WORKSPACE" ]; then
  echo "Error: directory not found: $WORKSPACE" >&2
  exit 1
fi

echo "Auditing repos in: $WORKSPACE"
echo "---"

for dir in "$WORKSPACE"/*/; do
  [ -d "$dir" ] || continue
  repo=$(basename "$dir")
  config="$dir/docs/superpowers/plan-config.yaml"
  if [ -f "$config" ]; then
    if grep -q '^dispatch:$' "$config" 2>/dev/null; then
      echo "$repo: HAS dispatch block"
    elif grep -q '^dispatch: false' "$config" 2>/dev/null; then
      echo "$repo: dispatch: false (explicit local-only)"
    else
      echo "$repo: NO dispatch block (local-only)"
    fi
  else
    echo "$repo: NO plan-config.yaml"
  fi
done
