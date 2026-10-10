#!/usr/bin/env bash
# Installed real CLI/runner with explicitly synthetic forge and herdr inputs.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
work="$(mktemp -d)"
cache="$work/cache"
if [ -d /dev/shm ] && [ -w /dev/shm ]; then cache="$(mktemp -d /dev/shm/fr-replace-scenario.XXXXXX)"; fi
trap 'rm -rf "$work" "$cache"' EXIT
export FR_HERDR_CACHE_DIR="$cache" FR_TRIAGE_LOCK_DIR="$cache/locks"
export HERDR_SOCKET_PATH="$work/server.sock" HERDR_ENV=1 HERDR_PANE_ID=w0:p0
export HERDR_REPLACE_STATE="$work/pane.json" HERDR_REPLACE_LOG="$work/keys"
export SCENARIO_PY="$(candidate_python)" SCENARIO_HELPER="$here/fixtures/herdr-batch-replace.py"
mkdir -p "$work/bin"
printf '#!/bin/sh\nexec "$SCENARIO_PY" "$SCENARIO_HELPER" "$@"\n' > "$work/bin/herdr"
chmod +x "$work/bin/herdr"
export PATH="$work/bin:$PATH"
"$SCENARIO_PY" "$SCENARIO_HELPER" scenario-run
echo 'ok: herdr-batch-replace'
