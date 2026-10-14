#!/usr/bin/env bash
# Installed candidate CLI/runner; all external observations/effects are fake-backed.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
work="$(mktemp -d)"
cache="$work/cache"
if [ -d /dev/shm ] && [ -w /dev/shm ]; then cache="$(mktemp -d /dev/shm/fr-recovery-scenario.XXXXXX)"; fi
trap 'rm -rf "$work" "$cache"' EXIT
export FR_HERDR_CACHE_DIR="$cache" FR_TRIAGE_LOCK_DIR="$cache/locks"
export HERDR_SOCKET_PATH="$work/server.sock" HERDR_ENV=1 HERDR_PANE_ID=caller HERDR_WORKSPACE_ID=w1T
mkdir -p "$work/repo"
git init -q "$work/repo"
(
  cd "$work/repo"
  "$(candidate_python)" "$here/fixtures/triage-closed-recovery.py"
)
echo 'ok: triage-closed-recovery'
