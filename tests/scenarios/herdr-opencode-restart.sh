#!/usr/bin/env bash
# Installed CLI with synthetic herdr process state and captured input observations.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
export FR_HERDR_CACHE_DIR="$work/cache" HERDR_SOCKET_PATH="$work/server.sock"
export HERDR_ENV=1 HERDR_PANE_ID=w0:p0 HERDR_FAKE_STATE="$work/state"
export HERDR_FAKE_LOG="$work/log"
IFS= read -r shebang < "$(command -v fr)"
export SCENARIO_PY="${shebang#\#!}" SCENARIO_HELPER="$here/fixtures/herdr-opencode.py"
mkdir -p "$work/bin"
printf '#!/bin/sh\nexec "$SCENARIO_PY" "$SCENARIO_HELPER" "$@"\n' > "$work/bin/herdr"
chmod +x "$work/bin/herdr"
export PATH="$work/bin:$PATH"
"$SCENARIO_PY" "$SCENARIO_HELPER" scenario-prepare
out="$(fr-herdr restart-idle)"
expect_grep '1 would restart' "$out" 'known captured input is eligible'
[ ! -s "$HERDR_FAKE_STATE" ] || fail 'preview mutated state'
out="$(fr-herdr restart-idle --yes)"
expect_grep '1 restarted' "$out" 'fresh restart took up durable HOLD'
expect_grep 'HOLD' "$(<"$HERDR_FAKE_LOG")" 'recovered delivery stays held'
out="$(fr-herdr restart-idle --yes --exclude w1:p1)"
expect_grep 'skip.*excluded' "$out" 'excluded pane receives no input'
echo "ok: herdr-opencode-restart"
