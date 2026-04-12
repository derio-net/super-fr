#!/usr/bin/env bash
# Smoke test the vk CLI and verify dispatch gate behavior.
# Usage: smoke-test.sh <workspace-dir> <dispatch-repo> <local-repo>
#
# Run from the superpowers-for-vk repo root (where vk is installed).
# Example: ./scripts/migration/smoke-test.sh ~/Docs/projects/HOMELAB superpowers-for-vk kid-laptops

set -euo pipefail

WORKSPACE="${1:?Usage: smoke-test.sh <workspace-dir> <dispatch-repo> <local-repo>}"
DISPATCH_REPO="${2:?Missing dispatch-repo argument}"
LOCAL_REPO="${3:?Missing local-repo argument}"

# Resolve vk binary from the current project's venv (must run from superpowers-for-vk root)
VK="$(uv run which vk 2>/dev/null || echo "")"
if [ -z "$VK" ]; then
  echo "Error: vk not found. Run this script from the superpowers-for-vk repo root." >&2
  exit 1
fi
echo "Using vk at: $VK"

echo ""
echo "=== VK CLI Smoke Test ==="
echo ""

echo "--- CLI basics ---"
"$VK" --version
"$VK" --help >/dev/null && echo "vk --help: OK"
"$VK" plan --help >/dev/null && echo "vk plan --help: OK"
"$VK" dispatch --help >/dev/null && echo "vk dispatch --help: OK"
"$VK" progress --help >/dev/null && echo "vk progress --help: OK"
"$VK" execute --help >/dev/null && echo "vk execute --help: OK"
echo ""

echo "--- Dispatch-enabled repo: $DISPATCH_REPO ---"
dispatch_dir="$WORKSPACE/$DISPATCH_REPO"
if [ -d "$dispatch_dir" ]; then
  first_plan=$(find "$dispatch_dir/docs/superpowers/plans/" -name "*.md" 2>/dev/null | head -1)
  if [ -n "$first_plan" ]; then
    (cd "$dispatch_dir" && "$VK" dispatch "$first_plan" --dry-run) && echo "Dispatch dry-run: OK" || echo "Dispatch dry-run: FAILED (exit $?)"
  else
    echo "No plans found in $DISPATCH_REPO"
  fi
else
  echo "Repo not found: $dispatch_dir"
fi
echo ""

echo "--- Local-only repo: $LOCAL_REPO ---"
local_dir="$WORKSPACE/$LOCAL_REPO"
if [ -d "$local_dir" ]; then
  (cd "$local_dir" && "$VK" progress board) && echo "Progress board: OK" || echo "Progress board: FAILED (exit $?)"

  first_plan=$(find "$local_dir/docs/superpowers/plans/" -name "*.md" 2>/dev/null | head -1)
  if [ -n "$first_plan" ]; then
    (cd "$local_dir" && "$VK" dispatch "$first_plan" --dry-run 2>&1) && echo "Gate FAILED (should have refused)" || echo "Gate refusal: OK (exit $?)"
  else
    echo "No plans in $LOCAL_REPO to test gate refusal"
  fi
else
  echo "Repo not found: $local_dir"
fi

echo ""
echo "=== Smoke test complete ==="
