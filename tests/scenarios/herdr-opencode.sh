#!/usr/bin/env bash
# Installed runner against explicitly synthetic responses; no interactive live claim.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
export FR_HERDR_CACHE_DIR="$work/cache" HERDR_SOCKET_PATH="$work/server.sock"
py="$(candidate_python)"
"$py" "$here/fixtures/herdr-opencode.py" scenario-launch
echo "ok: herdr-opencode"
