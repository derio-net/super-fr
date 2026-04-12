#!/usr/bin/env bash
# Run vk init for all repos without a plan-config.yaml.
# Usage: init-unconfigured.sh <workspace-dir>

set -euo pipefail

WORKSPACE="${1:?Usage: init-unconfigured.sh <workspace-dir>}"

if [ ! -d "$WORKSPACE" ]; then
  echo "Error: directory not found: $WORKSPACE" >&2
  exit 1
fi

count=0
for dir in "$WORKSPACE"/*/; do
  [ -d "$dir" ] || continue
  repo=$(basename "$dir")
  config="$dir/docs/superpowers/plan-config.yaml"

  if [ ! -f "$config" ]; then
    echo "--- Initializing: $repo"
    (cd "$dir" && VK_REPO_ROOT="$dir" vk init)
    (cd "$dir" && git add docs/superpowers/ && git commit -m "chore: add plan-config.yaml (local-only, no dispatch)" || true)
    count=$((count + 1))
  fi
done

echo "---"
echo "Initialized $count repo(s)."
