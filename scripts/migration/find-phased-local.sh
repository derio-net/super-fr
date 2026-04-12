#!/usr/bin/env bash
# Find phased plans in local-only repos (candidates for flat conversion).
# Usage: find-phased-local.sh <workspace-dir>

set -euo pipefail

WORKSPACE="${1:?Usage: find-phased-local.sh <workspace-dir>}"

if [ ! -d "$WORKSPACE" ]; then
  echo "Error: directory not found: $WORKSPACE" >&2
  exit 1
fi

echo "Scanning for phased plans in local-only repos under: $WORKSPACE"
echo "---"

found=0
for dir in "$WORKSPACE"/*/; do
  [ -d "$dir" ] || continue
  config="$dir/docs/superpowers/plan-config.yaml"

  # Skip repos without config or with dispatch enabled
  [ -f "$config" ] || continue
  grep -q '^dispatch:$' "$config" 2>/dev/null && continue

  plans_dir="$dir/docs/superpowers/plans"
  [ -d "$plans_dir" ] || continue

  grep -rl '^## Phase ' "$plans_dir/" 2>/dev/null | while read -r plan; do
    echo "LOCAL-ONLY phased plan: $plan"
    echo "  Dry-run: vk plan convert $plan --to flat --dry-run"
    found=1
  done
done

if [ "$found" -eq 0 ]; then
  echo "No phased plans found in local-only repos."
fi
