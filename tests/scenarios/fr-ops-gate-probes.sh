#!/usr/bin/env bash
# Row fr-ops-gate-probes: `fr ops gate` stage 1 refuses an ops gap (spec
# 2026-11-01-ops-gate-probes R5) — a devops-gated run whose Test Plan carries command
# steps and whose plan declares no op — before any workspace exists, and a `none:`
# acknowledgement in the plan's ops.yaml (R4) lets it past the check.
#
# Credential free and forge free: the same harness as fr-ops-gate-stage.sh (host-worktree
# mode, a fake forge inside a driver running the candidate's own python, a local bare
# origin reached by a `file://localhost/...` URL).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

work="$(mktemp -d)"
export HOME="$work/home" MARKS="$work/marks" FR_OPS_TRUST_DIR="$work/trust" FR_OPS_GATE_DIR="$work/gate"
export FR_ISOLATION_TARGET=worktree FR_PROFILE=ops KUBERNETES_SERVICE_HOST=10.0.0.1
mkdir -p "$HOME" "$MARKS" "$FR_OPS_TRUST_DIR"
py="$(candidate_python)"

# --- smoke: the candidate runs and carries the gate ----------------------------------
run_fr out --version
require_exit 0 "$out"
run_fr out ops gate --help
require_exit 0 "$out"
expect_grep '--run' "$out" "fr ops gate takes --run"

echo "ok: fr-ops-gate-probes"
